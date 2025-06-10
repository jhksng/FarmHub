import time
import threading
from datetime import datetime, timedelta
from flask import Flask, request, render_template_string
import mysql.connector

# RPi.GPIO 라이브러리 임포트
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    print("RPi.GPIO 라이브러리를 찾을 수 없습니다. GPIO 제어는 비활성화됩니다.")
    print("라즈베리파이가 아닌 환경이거나, 라이브러리가 설치되지 않았을 수 있습니다.")
    GPIO_AVAILABLE = False
    # GPIO가 없어도 가상으로 동작하도록 더미 클래스 정의
    class DummyGPIO:
        def setmode(self, mode): pass
        def setup(self, pin, mode, initial=None): pass
        def output(self, pin, value): pass
        def cleanup(self): pass
        BCM = 11
        OUT = 0
        LOW = 0
        HIGH = 1
    GPIO = DummyGPIO()

app = Flask(__name__)

# 가상 핀 설정 (BCM 핀 번호 사용)
pins = {
    'LED': 5,
    'CoolerA': 6,
    'CoolerB': 13,
    'WaterPump': 19,
    'PTC': 26
}

# 릴레이 모듈은 LOW 신호에 작동(Active Low)하는 것을 가정
# state: 초기 상태는 모두 꺼짐 (HIGH)
state = {pin_num: GPIO.HIGH for pin_num in pins.values()}

# GPIO 핀 초기 설정
if GPIO_AVAILABLE:
    GPIO.setmode(GPIO.BCM)
    for pin_name, pin_num in pins.items():
        GPIO.setup(pin_num, GPIO.OUT, initial=GPIO.HIGH)
    print("GPIO 핀 초기 설정 완료.")

# 전역 제어 변수
current_loop_thread = None
current_crop_name = None
stop_event = threading.Event()

# --- 데이터베이스 관련 함수 ---

def get_db_connection():
    """데이터베이스 연결 객체를 반환합니다."""
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="1234",
        database="sensor"
    )

def get_crop_id(cursor, crop_name):
    """작물 이름으로 crop_info 테이블에서 ID를 조회합니다."""
    cursor.execute("SELECT id FROM crop_info WHERE crop = %s", (crop_name,))
    result = cursor.fetchone()
    return result[0] if result else None

def load_crop_settings(crop_name):
    """crop_info 테이블에서 특정 작물의 설정값을 불러옵니다."""
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT target_temp, target_humi, target_light, target_soil FROM crop_info WHERE crop = %s", (crop_name,))
    result = cursor.fetchone()
    cursor.close()
    db.close()
    if result:
        return {
            'temp': result[0],
            'humi': result[1],
            'light_duration': result[2], # 시간 단위
            'soil': result[3]
        }
    return None

def get_latest_sensor_values(crop_name):
    """sensor_log 테이블에서 가장 최신 센서 데이터를 가져옵니다."""
    db = get_db_connection()
    cursor = db.cursor()
    
    # 작물 이름으로 crop_id를 먼저 조회
    crop_id = get_crop_id(cursor, crop_name)
    if not crop_id:
        print(f"'{crop_name}'에 해당하는 crop_id를 찾을 수 없습니다.")
        cursor.close()
        db.close()
        return None

    # crop_id를 사용하여 sensor_log 조회
    cursor.execute("""
        SELECT temp, humi, soil, timestamp FROM sensor_log
        WHERE crop_id = %s
        ORDER BY timestamp DESC LIMIT 1
    """, (crop_id,))
    result = cursor.fetchone()
    cursor.close()
    db.close()
    if result:
        return {
            'temp': result[0],
            'humi': result[1],
            'soil': result[2],
            'timestamp': result[3]
        }
    return None


# --- 장치 제어 및 루틴 ---

def control_device(name, value):
    """지정된 장치의 GPIO 핀을 제어합니다."""
    pin_num = pins[name]
    state[pin_num] = value
    if GPIO_AVAILABLE:
        GPIO.output(pin_num, value)
    action = "켜짐 (LOW)" if value == GPIO.LOW else "꺼짐 (HIGH)"
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {name} 제어: {action} (핀: GPIO {pin_num})")

def water_pump_routine():
    """워터펌프를 10초간 작동시키는 루틴입니다."""
    print("워터펌프 작동 시작")
    control_device('WaterPump', GPIO.LOW)
    time.sleep(10)
    control_device('WaterPump', GPIO.HIGH)
    print("워터펌프 작동 종료")

def heater_routine():
    """PTC 히터를 60초간 작동시키는 루틴입니다."""
    print("히터 작동 시작")
    control_device('PTC', GPIO.LOW)
    time.sleep(60)
    control_device('PTC', GPIO.HIGH)
    print("히터 작동 종료")


# --- 메인 제어 루프 ---

def start_control_loop(crop_name, stop_event):
    """주기적으로 센서값을 확인하고 장치를 제어하는 메인 루프입니다."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] '{crop_name}' 작물 제어 루프 시작됨.")

    last_water_time = datetime.min
    last_soil_check_timestamp = None
    last_heat_time = datetime.min
    last_temp_check_timestamp = None
    water_cooldown_seconds = 600  # 10분
    heater_cooldown_seconds = 600 # 10분

    loop_count = 0
    while not stop_event.is_set():
        loop_count += 1
        print(f"\n--- {loop_count}번째 루프 ({crop_name}) ---")

        # DB에서 현재 선택된 작물과 LED 시작 시간 정보를 가져옴
        db = get_db_connection()
        cursor = db.cursor()
        try:
            # users 테이블에 데이터가 1개만 있다고 가정
            cursor.execute("SELECT selected_crop, selected_time FROM users LIMIT 1")
            user_selection = cursor.fetchone()
        except mysql.connector.Error as err:
            print(f"DB 오류 (users 조회): {err}")
            cursor.close()
            db.close()
            time.sleep(10)
            continue
        
        cursor.close()
        db.close()

        if not user_selection or user_selection[0] != crop_name:
            new_crop_name = user_selection[0] if user_selection else "없음"
            print(f"작물 변경 감지: {crop_name} -> {new_crop_name}. 현재 루프를 종료합니다.")
            stop_event.set()
            break

        led_start_time = user_selection[1] # users.selected_time 값

        crop_settings = load_crop_settings(crop_name)
        sensor = get_latest_sensor_values(crop_name)
        now = datetime.now()

        if not crop_settings or not sensor:
            print(f"'{crop_name}'에 대한 설정 또는 센서 데이터가 없습니다. 10초 대기.")
            time.sleep(10)
            continue

        # --- 생장등 제어 (DB의 selected_time 기준) ---
        target_light_duration_hours = crop_settings['light_duration']
        
        # 1. LED가 꺼져 있고, 시작 시간이 기록되지 않은(NULL) 경우 -> LED 켜기
        if state[pins['LED']] == GPIO.HIGH and led_start_time is None:
            control_device('LED', GPIO.LOW) # LED 켜기
            # DB에 LED 시작 시간 기록
            db_conn_update = get_db_connection()
            cursor_update = db_conn_update.cursor()
            cursor_update.execute("UPDATE users SET selected_time = %s LIMIT 1", (now,))
            db_conn_update.commit()
            cursor_update.close()
            db_conn_update.close()
            print(f"[{now.strftime('%H:%M:%S')}] 생장등 켜짐. DB에 시작 시간 기록. (목표: {target_light_duration_hours}시간)")

        # 2. LED가 켜져 있고, 시작 시간이 기록된 경우 -> 시간 확인 후 끄기
        elif state[pins['LED']] == GPIO.LOW and led_start_time is not None:
            total_duration_seconds = target_light_duration_hours * 3600
            elapsed_seconds = (now - led_start_time).total_seconds()

            if elapsed_seconds >= total_duration_seconds:
                control_device('LED', GPIO.HIGH) # LED 끄기
                # DB의 LED 시작 시간 초기화 (NULL)
                db_conn_update = get_db_connection()
                cursor_update = db_conn_update.cursor()
                cursor_update.execute("UPDATE users SET selected_time = NULL LIMIT 1")
                db_conn_update.commit()
                cursor_update.close()
                db_conn_update.close()
                print(f"[{now.strftime('%H:%M:%S')}] 생장등 목표 시간 완료. 꺼짐. DB 시간 초기화.")
            else:
                remaining_time = timedelta(seconds=int(total_duration_seconds - elapsed_seconds))
                print(f"[{now.strftime('%H:%M:%S')}] 생장등 켜짐. 남은 시간: {remaining_time}")
        
        # --- 워터펌프 제어 ---
        if (sensor['soil'] < crop_settings['soil'] and
            (sensor['timestamp'] != last_soil_check_timestamp or last_soil_check_timestamp is None) and
            (now - last_water_time).total_seconds() >= water_cooldown_seconds):
            
            print(f"토양 수분 부족 ({sensor['soil']:.1f}% < 목표 {crop_settings['soil']}%) → 워터펌프 작동")
            threading.Thread(target=water_pump_routine).start()
            last_water_time = now
            last_soil_check_timestamp = sensor['timestamp']

        # --- 히터/쿨러 제어 ---
        if (sensor['temp'] < crop_settings['temp'] - 2 and
            (sensor['timestamp'] != last_temp_check_timestamp or last_temp_check_timestamp is None) and
            (now - last_heat_time).total_seconds() >= heater_cooldown_seconds):
            
            print(f"온도 낮음 ({sensor['temp']:.1f}°C < 목표 {crop_settings['temp'] - 2}°C) → 히터 작동")
            threading.Thread(target=heater_routine).start()
            last_heat_time = now
            last_temp_check_timestamp = sensor['timestamp']
        
        elif sensor['temp'] > crop_settings['temp'] + 2:
            if state[pins['CoolerA']] == GPIO.HIGH: # 쿨러가 꺼져있을 때만 메시지 출력
                print(f"온도 높음 ({sensor['temp']:.1f}°C > 목표 {crop_settings['temp'] + 2}°C) → 쿨러 작동")
            control_device('CoolerA', GPIO.LOW)
            control_device('CoolerB', GPIO.LOW)
        else:
            if state[pins['CoolerA']] == GPIO.LOW: # 쿨러가 켜져있을 때만 메시지 출력
                print(f"온도 적정 ({sensor['temp']:.1f}°C) → 쿨러 꺼짐")
            control_device('CoolerA', GPIO.HIGH)
            control_device('CoolerB', GPIO.HIGH)

        time.sleep(10)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] '{crop_name}' 제어 루프 정상적으로 종료됨.")


# --- Flask 웹 인터페이스 ---

def render_form(message=None):
    """사용자 입력을 위한 HTML 폼을 렌더링합니다."""
    return render_template_string('''
        <!doctype html>
        <html lang="ko">
        <head>
            <meta charset="UTF-8">
            <title>작물 제어 시작</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f4; color: #333; }
                h2 { color: #0056b3; }
                form { background-color: #fff; padding: 25px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); display: inline-block; }
                input[type="text"], input[type="submit"] { padding: 10px 15px; margin: 8px 0; display: block; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; width: 100%; }
                input[type="submit"] { background-color: #28a745; color: white; cursor: pointer; font-size: 16px; font-weight: bold; }
                input[type="submit"]:hover { background-color: #218838; }
                .message { margin-top: 20px; padding: 15px; background-color: #e9ecef; border: 1px solid #ced4da; border-radius: 5px; }
            </style>
        </head>
        <body>
            <h2>작물 이름을 입력하세요</h2>
            <form method="post">
                <input type="text" name="crop" placeholder="예: Apple" required>
                <input type="submit" value="제어 시작">
            </form>
            {% if message %}
                <div class="message">{{ message | safe }}</div>
            {% endif %}
        </body>
        </html>
    ''', message=message)

@app.route('/', methods=['GET', 'POST'])
def index():
    """메인 페이지 라우트, 작물 선택 및 제어 루프 시작/전환을 처리합니다."""
    global current_loop_thread, current_crop_name, stop_event
    message = None

    if request.method == 'POST':
        crop_name = request.form['crop'].strip()

        if not crop_name:
            return render_form(message="작물 이름을 입력해주세요.")
        
        db = get_db_connection()
        cursor = db.cursor()
        try:
            # 1. crop_info 테이블에 해당 작물이 있는지 유효성 검사
            cursor.execute("SELECT crop FROM crop_info WHERE crop = %s", (crop_name,))
            if not cursor.fetchone():
                message = f"오류: '{crop_name}'은(는) 유효한 작물이 아닙니다. 'crop_info' 테이블을 확인해주세요."
                return render_form(message=message)

            # 2. 기존 제어 루프가 있다면 종료
            if current_loop_thread and current_loop_thread.is_alive():
                print("기존 제어 루프 종료 요청...")
                stop_event.set()
                current_loop_thread.join(timeout=5)
                if current_loop_thread.is_alive():
                    print("경고: 기존 제어 루프가 5초 내에 정상 종료되지 않았습니다.")
                print("기존 제어 루프 종료 완료.")

            # 3. users 테이블 업데이트 (새 작물 선택, LED 시간 초기화)
            #    users 테이블에 사용자가 1명(row가 1개)이라고 가정
            cursor.execute("UPDATE users SET selected_crop = %s, selected_time = NULL LIMIT 1", (crop_name,))
            db.commit()
            print(f"[DB] users 테이블 업데이트: selected_crop='{crop_name}', selected_time=NULL")

            # 4. 새 제어 루프 시작
            stop_event = threading.Event() # 새 루프를 위한 새 이벤트 객체
            current_crop_name = crop_name
            current_loop_thread = threading.Thread(target=start_control_loop, args=(crop_name, stop_event), daemon=True)
            current_loop_thread.start()
            print(f"'{crop_name}' 작물에 대한 새 제어 루프 시작 요청됨.")
            message = f"<h3>'{crop_name}' 작물 제어 루프를 시작합니다.</h3><p>자세한 동작 상태는 콘솔 로그를 확인해주세요.</p>"

        except mysql.connector.Error as err:
            message = f"데이터베이스 오류: {err}"
            print(f"데이터베이스 오류: {err}")
        finally:
            cursor.close()
            db.close()

    return render_form(message=message)

@app.teardown_appcontext
def teardown_gpio(exception=None):
    """Flask 앱 컨텍스트가 종료될 때 호출되지만, 별도 정리 로직은 메인 실행부에 있습니다."""
    pass

if __name__ == '__main__':
    try:
        # debug=True는 코드 변경 시 서버를 재시작하여 스레드나 GPIO 상태에 문제를 일으킬 수 있으므로
        # 실제 운영 시에는 False로 두는 것을 권장합니다.
        app.run(host='0.0.0.0', port=5000, debug=False)
    finally:
        # 프로그램이 어떤 이유로든 종료될 때(Ctrl+C 등) GPIO 핀을 초기 상태로 되돌립니다.
        if GPIO_AVAILABLE:
            print("애플리케이션을 종료하며 GPIO.cleanup()을 실행합니다.")
            GPIO.cleanup()

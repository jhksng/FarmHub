import time
import threading
from datetime import datetime
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
    # GPIO가 없어도 가상으로 동작하도록 더미 함수 정의
    class DummyGPIO:
        def setmode(self, mode): pass
        def setup(self, pin, mode, initial=None): pass
        def output(self, pin, value): pass
        def cleanup(self): pass
        BCM = 11 # 실제 값과 무관하게 정의
        OUT = 0 # 실제 값과 무관하게 정의
        LOW = 0 # 실제 값과 무관하게 정의
        HIGH = 1 # 실제 값과 무관하게 정의
    GPIO = DummyGPIO() # 더미 GPIO 객체 사용

app = Flask(__name__)

# 가상 핀 설정 (BCM 핀 번호 사용 가정)
# 반드시 라즈베리파이 핀아웃을 확인하고 실제 연결된 GPIO BCM 번호로 변경하세요!
pins = {
    'LED': 5,      # GPIO 5
    'CoolerA': 6,  # GPIO 6
    'CoolerB': 13, # GPIO 13
    'WaterPump': 19, # GPIO 19
    'PTC': 26      # GPIO 26
}

# ON = GPIO.LOW (0V), OFF = GPIO.HIGH (3.3V)
# 일반적으로 릴레이 모듈은 LOW 신호에 작동하는 경우가 많습니다 (Active Low).
# 만약 장치가 HIGH 신호에 작동한다면, 아래 state 초기값과 control_device 함수의 value를 반대로 설정하세요.
state = {pin_num: GPIO.HIGH for pin_num in pins.values()} # 초기 상태는 모두 꺼짐

# GPIO 핀 초기 설정
if GPIO_AVAILABLE:
    GPIO.setmode(GPIO.BCM) # BCM 핀 번호 모드 사용
    for pin_name, pin_num in pins.items():
        # 모든 핀을 출력 모드로 설정하고 초기 상태는 OFF (GPIO.HIGH)
        GPIO.setup(pin_num, GPIO.OUT, initial=GPIO.HIGH)
    print("GPIO 핀 초기 설정 완료.")

# 전역 제어 변수
current_loop_thread = None
current_crop_name = None
stop_event = threading.Event()

# DB 연결 함수
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="1234",
        database="sensor"
    )

# 작물 설정 가져오기
def load_crop_settings(crop_name):
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
            'light_duration': result[2],
            'soil': result[3]
        }
    return None

# 최신 센서값 가져오기
def get_latest_sensor_values(crop_name):
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("""
        SELECT temp, humi, soil, timestamp FROM sensor_log
        WHERE crop = %s
        ORDER BY timestamp DESC LIMIT 1
    """, (crop_name,))
    result = cursor.fetchone()
    db.close() # 커서 닫은 후 DB 연결 닫기
    if result:
        return {
            'temp': result[0],
            'humi': result[1],
            'soil': result[2],
            'timestamp': result[3]
        }
    return None

# 장치 제어 함수 (실제 GPIO 제어 로직 추가)
def control_device(name, value):
    pin_num = pins[name]
    state[pin_num] = value # 내부 상태 업데이트

    # 실제 GPIO 제어
    if GPIO_AVAILABLE:
        GPIO.output(pin_num, value)

    action = "켜짐 (GPIO.LOW)" if value == GPIO.LOW else "꺼짐 (GPIO.HIGH)"
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {name} 제어: {action} (핀: GPIO {pin_num})")

# 워터펌프 루틴
def water_pump_routine():
    print("워터펌프 작동 시작")
    control_device('WaterPump', GPIO.LOW) # ON
    time.sleep(10) # 10초 작동
    control_device('WaterPump', GPIO.HIGH) # OFF
    print("워터펌프 작동 종료")

# 히터 루틴
def heater_routine():
    print("히터 작동 시작")
    control_device('PTC', GPIO.LOW) # ON
    time.sleep(60) # 60초 작동
    control_device('PTC', GPIO.HIGH) # OFF
    print("히터 작동 종료")

# 제어 루프
def start_control_loop(crop_name, stop_event):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {crop_name} 제어 루프 시작됨.")

    light_timer = {'start_time': None, 'duration': 0, 'manual_off_time': None, 'remaining_extension': 0}
    last_water_time = datetime.min
    last_soil_check_timestamp = None
    last_heat_time = datetime.min
    last_temp_check_timestamp = None
    water_cooldown_seconds = 600 # 물주는 빈도 쿨다운 1분
    heater_cooldown_seconds = 600 # 히터 작동 빈도 쿨다운 1분

    loop_count = 0

    while not stop_event.is_set():
        loop_count += 1
        print(f"\n--- {loop_count}번째 루프 ({crop_name}) ---")

        # 현재 선택된 작물 이름을 DB에서 가져와서 제어 루프의 crop_name과 동기화
        # 이 부분을 매 루프마다 확인하여 다른 작물이 선택되면 현재 루프를 종료합니다.
        db_conn = get_db_connection()
        cursor = db_conn.cursor()
        try:
            cursor.execute("SELECT selected_crop FROM users LIMIT 1")
            db_selected_crop_result = cursor.fetchone()
        except mysql.connector.Error as err:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] DB에서 selected_crop 가져오기 오류: {err}")
            db_selected_crop_result = None
        finally:
            cursor.close()
            db_conn.close()

        if db_selected_crop_result and db_selected_crop_result[0] != crop_name:
            new_crop_name = db_selected_crop_result[0]
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 작물 변경 감지: {crop_name} -> {new_crop_name}. 제어 루프 종료 요청.")
            stop_event.set() # 새로운 작물이 선택되면 현재 루프를 종료
            break # while 루프를 빠져나감 (선호되는 방식)

        crop_settings = load_crop_settings(crop_name)
        sensor = get_latest_sensor_values(crop_name)
        now = datetime.now()

        if not crop_settings:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] '{crop_name}'에 대한 작물 설정이 없습니다. 10초 대기.")
            time.sleep(10)
            continue
        if not sensor:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] '{crop_name}'에 대한 센서 데이터가 없습니다. 10초 대기.")
            time.sleep(10)
            continue

        # 생장등 제어
        if light_timer['start_time'] is None:
            # 아직 LED를 켜지 않았거나, 한 사이클이 끝나면 새로 시작
            light_timer['start_time'] = now
            light_timer['duration'] = crop_settings['light_duration'] # 시간 단위
            control_device('LED', GPIO.LOW) # LED 켜기 (ON)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 생장등 켜짐 (목표 {light_timer['duration']}시간)")
        elif state[pins['LED']] == GPIO.LOW: # LED가 켜져 있는 상태라면
            total_duration_seconds = light_timer['duration'] * 3600 + light_timer['remaining_extension']
            elapsed_seconds = (now - light_timer['start_time']).total_seconds()

            if elapsed_seconds >= total_duration_seconds:
                control_device('LED', GPIO.HIGH) # LED 끄기 (OFF)
                light_timer['start_time'] = None # 다음 사이클을 위해 타이머 초기화
                light_timer['remaining_extension'] = 0 # 확장 시간 초기화
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 생장등 켜진 시간 완료. 꺼짐.")
            else:
                remaining_time_seconds = total_duration_seconds - elapsed_seconds
                hours = int(remaining_time_seconds // 3600)
                minutes = int((remaining_time_seconds % 3600) // 60)
                seconds = int(remaining_time_seconds % 60)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 생장등 켜짐. 남은 시간: {hours}시간 {minutes}분 {seconds}초")


        # 워터펌프 조건
        # 토양 습도가 설정값보다 낮고, 센서 타임스탬프가 마지막 체크 타임스탬프와 다르거나 (새로운 데이터), 쿨다운 시간이 지났으면
        if (sensor['soil'] < crop_settings['soil'] and
            (sensor['timestamp'] != last_soil_check_timestamp or last_soil_check_timestamp is None) and
            (now - last_water_time).total_seconds() >= water_cooldown_seconds):

            print(f"[{datetime.now().strftime('%H:%M:%S')}] 토양 수분 부족 ({sensor['soil']:.1f}% < 목표 {crop_settings['soil']}%) → 워터펌프 작동")
            # 스레딩으로 워터펌프 루틴을 실행하여 메인 제어 루프가 블록되지 않도록 함
            threading.Thread(target=water_pump_routine).start()
            last_water_time = now # 마지막 워터펌프 작동 시간 업데이트
            last_soil_check_timestamp = sensor['timestamp'] # 최신 센서 타임스탬프 기록 (중복 작동 방지)

        # 히터 조건
        # 온도가 목표 온도보다 2도 이상 낮고, 센서 타임스탬프가 마지막 체크 타임스탬프와 다르거나 (새로운 데이터), 쿨다운 시간이 지났으면
        if (sensor['temp'] < crop_settings['temp'] - 2 and
            (sensor['timestamp'] != last_temp_check_timestamp or last_temp_check_timestamp is None) and
            (now - last_heat_time).total_seconds() >= heater_cooldown_seconds):

            print(f"[{datetime.now().strftime('%H:%M:%S')}] 온도 낮음 ({sensor['temp']:.1f}°C < 목표 {crop_settings['temp'] - 2}°C) → 히터 작동")
            threading.Thread(target=heater_routine).start()
            last_heat_time = now # 마지막 히터 작동 시간 업데이트
            last_temp_check_timestamp = sensor['timestamp'] # 최신 센서 타임스탬프 기록 (중복 작동 방지)

        # 쿨러 조건 (상시 체크)
        elif sensor['temp'] > crop_settings['temp'] + 2:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 온도 높음 ({sensor['temp']:.1f}°C > 목표 {crop_settings['temp'] + 2}°C) → 쿨러 작동")
            control_device('CoolerA', GPIO.LOW) # ON
            control_device('CoolerB', GPIO.LOW) # ON
        else: # 온도가 적정 범위에 있으면 쿨러 끔
            # 쿨러가 켜져 있었다면 끔 (불필요한 제어 메시지 출력 방지)
            if state[pins['CoolerA']] == GPIO.LOW or state[pins['CoolerB']] == GPIO.LOW:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 온도 적정 ({sensor['temp']:.1f}°C) → 쿨러 꺼짐")
                control_device('CoolerA', GPIO.HIGH) # OFF
                control_device('CoolerB', GPIO.HIGH) # OFF

        time.sleep(10) # 10초마다 루프 재실행

    print(f"[{datetime.now().strftime('%H:%M:%S')}] {crop_name} 제어 루프 종료됨.")

# 웹 입력 폼
def render_form(message=None):
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
                input[type="text"], input[type="submit"] {
                    padding: 10px 15px;
                    margin: 8px 0;
                    display: block;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    box-sizing: border-box;
                    width: 100%;
                }
                input[type="submit"] {
                    background-color: #28a745;
                    color: white;
                    cursor: pointer;
                    font-size: 16px;
                    font-weight: bold;
                }
                input[type="submit"]:hover {
                    background-color: #218838;
                }
                .message {
                    margin-top: 20px;
                    padding: 15px;
                    background-color: #e9ecef;
                    border: 1px solid #ced4da;
                    border-radius: 5px;
                }
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
    ''')

# 메인 웹 라우트
@app.route('/', methods=['GET', 'POST'])
def index():
    global current_loop_thread, current_crop_name, stop_event

    message = None

    if request.method == 'POST':
        crop_name = request.form['crop'].strip() # 공백 제거

        if not crop_name:
            message = "작물 이름을 입력해주세요."
            return render_form(message=message)
        
        db = get_db_connection()
        cursor = db.cursor()

        try:
            # 1. crop_info 테이블에 해당 작물이 있는지 확인 (유효성 검사)
            cursor.execute("SELECT crop FROM crop_info WHERE crop = %s", (crop_name,))
            if not cursor.fetchone():
                message = f"오류: '{crop_name}'은(는) 유효한 작물 이름이 아닙니다. 'crop_info' 테이블을 확인해주세요."
                return render_form(message=message)

            # 2. users 테이블의 selected_crop 필드를 업데이트 (항상 1개의 행만 있다고 가정)
            cursor.execute("UPDATE users SET selected_crop = %s", (crop_name,))
            db.commit()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [DB] users.selected_crop 업데이트: {crop_name}")

            # 기존 제어 루프 종료
            if current_loop_thread and current_loop_thread.is_alive():
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 기존 제어 루프 종료 요청됨.")
                stop_event.set()
                current_loop_thread.join(timeout=5) # 5초 대기 후 종료
                if current_loop_thread.is_alive():
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 경고: 기존 제어 루프가 5초 내에 종료되지 않았습니다.")
                stop_event = threading.Event() # 새로운 이벤트 객체 생성
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 기존 제어 루프 종료 완료.")


            # 새 제어 루프 시작
            current_crop_name = crop_name
            current_loop_thread = threading.Thread(target=start_control_loop, args=(crop_name, stop_event), daemon=True)
            current_loop_thread.start()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 새 제어 루프 ({crop_name}) 시작 요청됨.")

            message = f"<h3>'{crop_name}' 작물 제어 루프를 시작합니다.</h3><p>이 페이지는 제어 루프의 실행 상태를 직접 보여주지 않습니다. 콘솔/로그를 확인해주세요.</p>"

        except mysql.connector.Error as err:
            message = f"데이터베이스 오류: {err}"
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 데이터베이스 오류: {err}")
        finally:
            cursor.close()
            db.close()

    return render_form(message=message)

# Flask 앱이 종료될 때 GPIO 리소스를 정리
@app.teardown_appcontext
def teardown_gpio(exception=None):
    if GPIO_AVAILABLE:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 애플리케이션 종료 시 GPIO.cleanup() 실행.")
        GPIO.cleanup()

if __name__ == '__main__':
    # Flask 앱이 시작될 때 GPIO 초기 설정
    # 이 부분은 GPIO.setmode와 GPIO.setup을 이미 파일 상단에서 처리하므로 삭제
    # 다만, 애플리케이션 컨텍스트 외부에서 GPIO 설정이 필요하다면 여기에 위치시킬 수 있습니다.
    
    app.run(host='0.0.0.0', port=5000, debug=True)

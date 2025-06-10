import time
import threading
from datetime import datetime
from flask import Flask, request, render_template_string
import mysql.connector

app = Flask(__name__)

# 가상 핀 설정
pins = {
    'LED': 5,
    'CoolerA': 6,
    'CoolerB': 13,
    'WaterPump': 19,
    'PTC': 26
}

# ON = 0, OFF = 1 (가정, 실제 GPIO 통신 시에는 다를 수 있음)
state = {pin: 1 for pin in pins.values()}

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

# 장치 제어 함수 (실제 GPIO 제어 로직은 여기에 들어감)
def control_device(name, value):
    state[pins[name]] = value # 가상 핀 상태 업데이트
    action = "켜짐" if value == 0 else "꺼짐"
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {name} 제어: {action} (핀: {pins[name]})")
    # TODO: 여기에 실제 GPIO 제어 코드 (예: RPi.GPIO.output(pins[name], value)) 추가

# 워터펌프 루틴
def water_pump_routine():
    print("워터펌프 작동 시작")
    control_device('WaterPump', 0) # ON
    time.sleep(10) # 10초 작동
    control_device('WaterPump', 1) # OFF
    print("워터펌프 작동 종료")

# 히터 루틴
def heater_routine():
    print("히터 작동 시작")
    control_device('PTC', 0) # ON
    time.sleep(60) # 60초 작동
    control_device('PTC', 1) # OFF
    print("히터 작동 종료")

# 제어 루프
def start_control_loop(crop_name, stop_event):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {crop_name} 제어 루프 시작됨.")

    light_timer = {'start_time': None, 'duration': 0, 'manual_off_time': None, 'remaining_extension': 0}
    last_water_time = datetime.min
    last_soil_check_timestamp = None
    last_heat_time = datetime.min
    last_temp_check_timestamp = None
    water_cooldown_seconds = 60
    heater_cooldown_seconds = 60

    loop_count = 0

    while not stop_event.is_set():
        loop_count += 1
        print(f"\n--- {loop_count}번째 루프 ({crop_name}) ---")

        # 현재 선택된 작물 이름을 DB에서 가져와서 제어 루프의 crop_name과 동기화
        db_conn = get_db_connection()
        cursor = db_conn.cursor()
        cursor.execute("SELECT selected_crop FROM users LIMIT 1")
        db_selected_crop_result = cursor.fetchone()
        cursor.close()
        db_conn.close()

        if db_selected_crop_result and db_selected_crop_result[0] != crop_name:
            new_crop_name = db_selected_crop_result[0]
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 작물 변경 감지: {crop_name} -> {new_crop_name}. 제어 루프 종료.")
            stop_event.set() # 새로운 작물이 선택되면 현재 루프를 종료
            continue # 루프 종료

        crop_settings = load_crop_settings(crop_name)
        sensor = get_latest_sensor_values(crop_name)
        now = datetime.now()

        if not crop_settings or not sensor:
            print("설정이나 센서값 없음. 10초 대기")
            time.sleep(10)
            continue

        # 생장등 제어 (현재는 타이머만 있음, 실제 광량 센서 추가 필요)
        if light_timer['start_time'] is None:
            light_timer['start_time'] = now
            light_timer['duration'] = crop_settings['light_duration'] # 시간 단위
            control_device('LED', 0) # LED 켜기
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 생장등 켜짐 (목표 {light_timer['duration']}시간)")
        elif state[pins['LED']] == 0: # LED가 켜져 있는 상태라면
            total_duration_seconds = light_timer['duration'] * 3600 + light_timer['remaining_extension']
            elapsed_seconds = (now - light_timer['start_time']).total_seconds()

            if elapsed_seconds >= total_duration_seconds:
                control_device('LED', 1) # LED 끄기
                light_timer['start_time'] = None # 다음 날을 위해 타이머 초기화
                light_timer['remaining_extension'] = 0 # 확장 시간 초기화
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 생장등 켜진 시간 완료. 꺼짐.")
            else:
                remaining_time_seconds = total_duration_seconds - elapsed_seconds
                hours = int(remaining_time_seconds // 3600)
                minutes = int((remaining_time_seconds % 3600) // 60)
                seconds = int(remaining_time_seconds % 60)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 생장등 켜짐. 남은 시간: {hours}시간 {minutes}분 {seconds}초")


        # 워터펌프 조건
        # 토양 습도가 설정값보다 낮고, 센서 타임스탬프가 마지막 체크 타임스탬프와 다르고, 쿨다운 시간이 지났으면
        if (sensor['soil'] < crop_settings['soil'] and
            (sensor['timestamp'] != last_soil_check_timestamp or last_soil_check_timestamp is None) and
            (now - last_water_time).total_seconds() >= water_cooldown_seconds):

            print(f"토양 수분 부족 ({sensor['soil']}% < 목표 {crop_settings['soil']}%) → 워터펌프 작동")
            threading.Thread(target=water_pump_routine).start()
            last_water_time = now
            last_soil_check_timestamp = sensor['timestamp'] # 최신 센서 타임스탬프 기록

        # 히터 조건
        # 온도가 목표 온도보다 2도 이상 낮고, 센서 타임스탬프가 마지막 체크 타임스탬프와 다르고, 쿨다운 시간이 지났으면
        if (sensor['temp'] < crop_settings['temp'] - 2 and
            (sensor['timestamp'] != last_temp_check_timestamp or last_temp_check_timestamp is None) and
            (now - last_heat_time).total_seconds() >= heater_cooldown_seconds):

            print(f"온도 낮음 ({sensor['temp']}°C < 목표 {crop_settings['temp'] - 2}°C) → 히터 작동")
            threading.Thread(target=heater_routine).start()
            last_heat_time = now
            last_temp_check_timestamp = sensor['timestamp'] # 최신 센서 타임스탬프 기록

        # 쿨러 조건 (상시 체크)
        elif sensor['temp'] > crop_settings['temp'] + 2:
            print(f"온도 높음 ({sensor['temp']}°C > 목표 {crop_settings['temp'] + 2}°C) → 쿨러 작동")
            control_device('CoolerA', 0) # ON
            control_device('CoolerB', 0) # ON
        else: # 온도가 적정 범위에 있으면 쿨러 끔
            if state[pins['CoolerA']] == 0 or state[pins['CoolerB']] == 0: # 쿨러가 켜져 있었다면 끔
                print(f"온도 적정 ({sensor['temp']}°C) → 쿨러 꺼짐")
                control_device('CoolerA', 1) # OFF
                control_device('CoolerB', 1) # OFF

        time.sleep(10) # 10초마다 루프 재실행

    print(f"[{datetime.now().strftime('%H:%M:%S')}] {crop_name} 제어 루프 종료됨.")

# 웹 입력 폼
def render_form():
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
            # 1. crop_info 테이블에 해당 작물이 있는지 확인 (선택 사항이지만, 오타 방지 및 유효성 검사에 좋음)
            cursor.execute("SELECT crop FROM crop_info WHERE crop = %s", (crop_name,))
            if not cursor.fetchone():
                message = f"오류: '{crop_name}'은(는) 유효한 작물 이름이 아닙니다. 'crop_info' 테이블을 확인해주세요."
                return render_form(message=message)

            # 2. users 테이블의 selected_crop 필드를 업데이트 (항상 1개의 행만 있다고 가정)
            # 만약 users 테이블에 행이 없다면 INSERT를, 있다면 UPDATE를 해야 합니다.
            # 가장 간단한 방법은 UPSERT (UPDATE OR INSERT) 로직을 사용하는 것입니다.
            # 여기서는 users 테이블에 최소 1개의 행이 있다고 가정하고 UPDATE만 합니다.
            # 만약 users 테이블에 행이 없을 수도 있다면, INSERT 로직을 추가해야 합니다.
            cursor.execute("UPDATE users SET selected_crop = %s", (crop_name,))
            db.commit()
            print(f"[DB] users.selected_crop 업데이트: {crop_name}")

            # 기존 제어 루프 종료
            if current_loop_thread and current_loop_thread.is_alive():
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 기존 제어 루프 종료 요청됨.")
                stop_event.set()
                current_loop_thread.join(timeout=5) # 5초 대기 후 종료
                if current_loop_thread.is_alive():
                    print("경고: 기존 제어 루프가 5초 내에 종료되지 않았습니다.")
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

if __name__ == '__main__':
    # 0.0.0.0으로 설정하면 외부에서도 접근 가능 (개발용)
    # 실제 운영 시에는 방화벽 설정 및 보안에 유의해야 합니다.
    app.run(host='0.0.0.0', port=5000, debug=True)

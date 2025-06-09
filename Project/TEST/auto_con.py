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

# ON = 0, OFF = 1
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

# 최신 센서값 가져오기 (작물 필터 포함)
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

# 장치 제어 함수
def control_device(name, value):
    state[pins[name]] = value
    action = "켜짐" if value == 0 else "꺼짐"
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {name} 제어: {action}")

# 워터펌프 루틴
def water_pump_routine():
    print("워터펌프 작동 시작")
    control_device('WaterPump', 0)
    time.sleep(10)
    control_device('WaterPump', 1)
    print("워터펌프 작동 종료")

# 히터 루틴
def heater_routine():
    print("히터 작동 시작")
    control_device('PTC', 0)
    time.sleep(60)
    control_device('PTC', 1)
    print("히터 작동 종료")

# 제어 루프 함수
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

        crop_settings = load_crop_settings(crop_name)
        sensor = get_latest_sensor_values(crop_name)
        now = datetime.now()

        if not crop_settings or not sensor:
            print("설정이나 센서값 없음. 10초 대기")
            time.sleep(10)
            continue

        # 생장등 제어
        if light_timer['start_time'] is None:
            light_timer['start_time'] = now
            light_timer['duration'] = crop_settings['light_duration']
            control_device('LED', 0)
        elif state[pins['LED']] == 0:
            total_duration = light_timer['duration'] * 3600 + light_timer['remaining_extension']
            if (now - light_timer['start_time']).total_seconds() >= total_duration:
                control_device('LED', 1)

        # 워터펌프 조건
        if (sensor['soil'] < crop_settings['soil'] and
            sensor['timestamp'] != last_soil_check_timestamp and
            (now - last_water_time).total_seconds() >= water_cooldown_seconds):

            print("토양 수분 부족 → 워터펌프 작동")
            threading.Thread(target=water_pump_routine).start()
            last_water_time = now
            last_soil_check_timestamp = sensor['timestamp']

        # 히터 조건
        if (sensor['temp'] < crop_settings['temp'] - 2 and
            sensor['timestamp'] != last_temp_check_timestamp and
            (now - last_heat_time).total_seconds() >= heater_cooldown_seconds):

            print("온도 낮음 → 히터 작동")
            threading.Thread(target=heater_routine).start()
            last_heat_time = now
            last_temp_check_timestamp = sensor['timestamp']

        # 쿨러 조건
        elif sensor['temp'] > crop_settings['temp'] + 2:
            print("온도 높음 → 쿨러 작동")
            control_device('CoolerA', 0)
            control_device('CoolerB', 0)
        else:
            control_device('CoolerA', 1)
            control_device('CoolerB', 1)

        time.sleep(10)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] {crop_name} 제어 루프 종료됨.")

# 웹 라우트
def render_form():
    return render_template_string('''
        <h2>작물 이름을 입력하세요</h2>
        <form method="post">
            <input name="crop" placeholder="예: Apple" required>
            <input type="submit" value="제어 시작">
        </form>
    ''')

@app.route('/', methods=['GET', 'POST'])
def index():
    global current_loop_thread, current_crop_name, stop_event

    if request.method == 'POST':
        crop_name = request.form['crop']

        # 기존 루프 종료
        if current_loop_thread and current_loop_thread.is_alive():
            stop_event.set()
            current_loop_thread.join()

        # 새 루프 시작
        stop_event = threading.Event()
        current_crop_name = crop_name
        current_loop_thread = threading.Thread(target=start_control_loop, args=(crop_name, stop_event), daemon=True)
        current_loop_thread.start()

        return f"<h3>{crop_name} 작물 제어 루프 시작됨.</h3>"

    return render_form()

if __name__ == '__main__':
    app.run(debug=True)

from flask import Flask, request, render_template_string
import time
import threading
from datetime import datetime
import mysql.connector

app = Flask(__name__)

# 핀 설정
pins = {
    'LED': 5,
    'CoolerA': 6,
    'CoolerB': 13,
    'WaterPump': 19,
    'PTC': 26
}

state = {pin: 1 for pin in pins.values()}

# DB 연결
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="1234",
        database="sensor"
    )

# crop 설정 로드
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

# crop별 최신 센서값
def get_latest_sensor_values(crop_name):
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("""
        SELECT temp, humi, soil, timestamp
        FROM sensor_log
        WHERE crop = %s
        ORDER BY timestamp DESC
        LIMIT 1
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

# 루틴 함수
def water_pump_routine():
    control_device('WaterPump', 0)
    time.sleep(10)
    control_device('WaterPump', 1)

def heater_routine():
    control_device('PTC', 0)
    time.sleep(60)
    control_device('PTC', 1)

# 제어 루프 함수
def start_control_loop(crop_name):
    light_timer = {'start_time': None, 'duration': 0, 'manual_off_time': None, 'remaining_extension': 0}
    last_water_time = datetime.min
    last_soil_check_timestamp = None
    last_heat_time = datetime.min
    last_temp_check_timestamp = None
    water_cooldown_seconds = 60
    heater_cooldown_seconds = 60
    loop_count = 0

    while True:
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

        # 워터펌프
        if (sensor['soil'] < crop_settings['soil'] and
            sensor['timestamp'] != last_soil_check_timestamp and
            (now - last_water_time).total_seconds() >= water_cooldown_seconds):
            threading.Thread(target=water_pump_routine).start()
            last_water_time = now
            last_soil_check_timestamp = sensor['timestamp']

        # 히터
        if (sensor['temp'] < crop_settings['temp'] - 2 and
            sensor['timestamp'] != last_temp_check_timestamp and
            (now - last_heat_time).total_seconds() >= heater_cooldown_seconds):
            threading.Thread(target=heater_routine).start()
            last_heat_time = now
            last_temp_check_timestamp = sensor['timestamp']

        # 쿨러
        elif sensor['temp'] > crop_settings['temp'] + 2:
            control_device('CoolerA', 0)
            control_device('CoolerB', 0)
        else:
            control_device('CoolerA', 1)
            control_device('CoolerB', 1)

        time.sleep(10)

# 웹 인터페이스
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        crop_name = request.form['crop']
        threading.Thread(target=start_control_loop, args=(crop_name,), daemon=True).start()
        return f"<h3>{crop_name} 작물에 대한 제어 루프가 시작되었습니다.</h3>"
    
    return render_template_string('''
        <h2>작물 이름을 입력하세요</h2>
        <form method="post">
            <input name="crop" placeholder="예: Apple" required>
            <input type="submit" value="제어 시작">
        </form>
    ''')

# Flask 실행
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

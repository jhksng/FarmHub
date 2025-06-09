import time
import threading
from datetime import datetime
import mysql.connector

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

# DB 연결

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="1234",
        database="sensor"
    )

# 현재 작물 가져오기

def get_current_crop():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT crop FROM crop_info WHERE id = 1")
    result = cursor.fetchone()
    cursor.close()
    db.close()
    return result[0] if result else None

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

def get_latest_sensor_values():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT temp, humi, soil, timestamp FROM sensor_log ORDER BY timestamp DESC LIMIT 1")
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

# 초기 변수들
light_timer = {'start_time': None, 'duration': 0, 'manual_off_time': None, 'remaining_extension': 0}
last_water_time = datetime.min
last_soil_check_timestamp = None
last_heat_time = datetime.min
last_temp_check_timestamp = None
water_cooldown_seconds = 60
heater_cooldown_seconds = 60

# 제어 루프

def control_loop():
    loop_count = 0
    global last_water_time, last_soil_check_timestamp, last_heat_time, last_temp_check_timestamp

    while True:
        loop_count += 1
        print(f"\n--- {loop_count}번째 루프 ---")

        selected_crop = get_current_crop()
        crop_settings = load_crop_settings(selected_crop)
        sensor = get_latest_sensor_values()
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

        # 온도 낮을 때 히터 작동
        if (sensor['temp'] < crop_settings['temp'] - 2 and
            sensor['timestamp'] != last_temp_check_timestamp and
            (now - last_heat_time).total_seconds() >= heater_cooldown_seconds):

            print("온도 낮음 → 히터 작동")
            threading.Thread(target=heater_routine).start()
            last_heat_time = now
            last_temp_check_timestamp = sensor['timestamp']

        # 온도 높을 때만 쿨러 작동
        elif sensor['temp'] > crop_settings['temp'] + 2:
            print("온도 높음 → 쿨러 작동")
            control_device('CoolerA', 0)
            control_device('CoolerB', 0)
        else:
            control_device('CoolerA', 1)
            control_device('CoolerB', 1)

        time.sleep(10)

# 시작
if __name__ == "__main__":
    control_loop()

import time
import threading
import mysql.connector
from datetime import datetime

# 가상 핀 설정
pins = {
    'LED': 5,
    'CoolerA': 6,
    'CoolerB': 13,
    'WaterPump': 19,
    'PTC': 26
}

# on = 0 (켜짐), off = 1 (꺼짐)
state = {pin: 1 for pin in pins.values()}
light_timer = {
    'start_time': None,
    'duration': 0,
    'manual_off_time': None,
    'remaining_extension': 0
}

# DB 연결 함수
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="1234",
        database="sensor"
    )

# 현재 작물 정보 가져오기
def get_current_crop():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT crop FROM crop_info WHERE id = 1")
    result = cursor.fetchone()
    cursor.close()
    db.close()
    return result[0] if result else None

# 작물 정보 로드
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

# 센서값 로드
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
    action = "켜짐" if value == 0 else "꺼짐"
    print(f"{name} 제어: {action}")
    state[pins[name]] = value

# 워터펌프 루틴
def water_pump_routine():
    print("워터펌프 작동 시작")
    control_device('WaterPump', 0)
    time.sleep(10)
    control_device('WaterPump', 1)
    print("워터펌프 작동 중지")

# 상태 저장 루프 (선택)
def insert_status_to_db(crop_name):
    db = get_db_connection()
    cursor = db.cursor()
    query = """
        INSERT INTO sensor_status (crop, led, coolerA, coolerB, waterpump, ptc)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    values = (
        crop_name,
        state[pins['LED']],
        state[pins['CoolerA']],
        state[pins['CoolerB']],
        state[pins['WaterPump']],
        state[pins['PTC']]
    )
    cursor.execute(query, values)
    db.commit()
    cursor.close()
    db.close()

# 자동 제어 루프
last_water_time = datetime.min
last_heat_time = datetime.min

def control_loop():
    global last_water_time, last_heat_time, light_timer

    while True:
        selected_crop = get_current_crop()
        crop_settings = load_crop_settings(selected_crop)

        if not crop_settings:
            time.sleep(10)
            continue

        sensor = get_latest_sensor_values()
        if not sensor:
            time.sleep(10)
            continue

        now = datetime.now()

        # 생장등 제어
        if light_timer['start_time'] is None:
            light_timer['start_time'] = now
            light_timer['duration'] = crop_settings['light_duration']
            print("생장등 자동 켜짐")
            control_device('LED', 0)
        elif state[pins['LED']] == 1:
            total_duration = light_timer['duration'] * 3600 + light_timer['remaining_extension']
            if (now - light_timer['start_time']).total_seconds() >= total_duration:
                print("생장등 자동 꺼짐 (시간 초과)")
                control_device('LED', 1)

        # 워터펌프 제어
        if sensor['soil'] < crop_settings['soil'] and (now - last_water_time).total_seconds() >= 60:
            print("토양 수분 부족 → 워터펌프 작동")
            threading.Thread(target=water_pump_routine).start()
            last_water_time = now

        # 습도 제어
        if sensor['humi'] > crop_settings['humi']:
            print("습도 높음 → 쿨러 작동")
            control_device('CoolerA', 1)
            control_device('CoolerB', 1)
        else:
            print("습도 적정 → 쿨러 정지")
            control_device('CoolerA', 0)
            control_device('CoolerB', 0)

        # 온도 제어
        if sensor['temp'] < crop_settings['temp'] - 2 and (now - last_heat_time).total_seconds() >= 120:
            print("온도 낮음 → 히터 작동")
            control_device('PTC', 1)
            time.sleep(120)
            control_device('PTC', 0)
            print("히터 정지 → 쿨러 작동")
            control_device('CoolerB', 1)
            time.sleep(60)
            control_device('CoolerB', 0)
            print("쿨러 정지")
            last_heat_time = now
        elif sensor['temp'] > crop_settings['temp'] + 2:
            print("온도 높음 → 쿨러 작동")
            control_device('CoolerA', 1)
            control_device('CoolerB', 1)

        time.sleep(10)

def status_log_loop():
    while True:
        selected_crop = get_current_crop()
        insert_status_to_db(selected_crop)
        time.sleep(60)

# 실행
if __name__ == "__main__":
    threading.Thread(target=control_loop, daemon=True).start()
    threading.Thread(target=status_log_loop, daemon=True).start()

    while True:
        time.sleep(1)  # 메인 스레드 유지용

from flask import Flask, render_template, request
import RPi.GPIO as GPIO
import time
import threading
import mysql.connector
from datetime import datetime, timedelta

app = Flask(__name__)

# GPIO 설정
GPIO.setmode(GPIO.BCM)
pins = {
    'LED': 5,
    'CoolerA': 6,
    'CoolerB': 13,
    'WaterPump': 19,
    'PTC': 26
}
for pin in pins.values():
    GPIO.setup(pin, GPIO.OUT)

state = {pin: 0 for pin in pins.values()}
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

# 작물 정보 로드
def load_crop_settings(crop_name):
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT target_temp, target_humi, target_light FROM crop_info WHERE crop = %s", (crop_name,))
    result = cursor.fetchone()
    cursor.close()
    db.close()
    if result:
        return {
            'temp': result[0],
            'humi': result[1],
            'light_duration': result[2]  # 시간 단위
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

# 상태 저장
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

# 제어 함수들
def control_device(name, value):
    GPIO.output(pins[name], value)
    state[pins[name]] = value

def water_pump_routine():
    control_device('WaterPump', 1)
    time.sleep(10)
    control_device('WaterPump', 0)

last_water_time = datetime.min
last_heat_time = datetime.min

# 제어 루프 쓰레드
def control_loop():
    global last_water_time, last_heat_time, light_timer

    selected_crop = "상추"
    crop_settings = load_crop_settings(selected_crop)

    while True:
        sensor = get_latest_sensor_values()
        if not sensor:
            time.sleep(10)
            continue

        now = datetime.now()

        # 생장등 제어
        if light_timer['start_time'] is None:
            light_timer['start_time'] = now
            light_timer['duration'] = crop_settings['light_duration']
            control_device('LED', 1)
        elif state[pins['LED']] == 1:
            total_duration = light_timer['duration'] * 3600 + light_timer['remaining_extension']
            if (now - light_timer['start_time']).total_seconds() >= total_duration:
                control_device('LED', 0)
                light_timer['manual_off_time'] = now
        elif state[pins['LED']] == 0 and light_timer['manual_off_time']:
            pass

        # 워터펌프 제어
        if sensor['soil'] < 300 and (now - last_water_time).total_seconds() >= 60:
            threading.Thread(target=water_pump_routine).start()
            last_water_time = now

        # 습도 제어
        if sensor['humi'] > crop_settings['humi']:
            control_device('CoolerA', 1)
            control_device('CoolerB', 1)
        else:
            control_device('CoolerA', 0)
            control_device('CoolerB', 0)

        # 온도 제어
        if sensor['temp'] < 16 and (now - last_heat_time).total_seconds() >= 120:
            control_device('PTC', 1)
            time.sleep(120)
            control_device('PTC', 0)
            control_device('CoolerB', 1)
            time.sleep(60)
            control_device('CoolerB', 0)
            last_heat_time = now
        elif sensor['temp'] > 20:
            control_device('CoolerA', 1)
            control_device('CoolerB', 1)

        time.sleep(10)

# 상태 저장 루프 쓰레드
def status_log_loop():
    selected_crop = "상추"
    while True:
        insert_status_to_db(selected_crop)
        time.sleep(60)

# 웹 라우터
@app.route('/control')
def control_page():
    selected_crop = "상추"
    return render_template('view_control.html', state=state, crop=selected_crop)


@app.route('/controller', methods=["POST"])
def controller():
    global light_timer
    for name in pins:
        if name in request.form:
            value = int(request.form[name])
            prev_value = state[pins[name]]
            control_device(name, value)

            # 생장등 수동 끄기/켜기 처리
            if name == 'LED':
                now = datetime.now()
                if prev_value == 1 and value == 0:
                    light_timer['manual_off_time'] = now
                elif prev_value == 0 and value == 1 and light_timer['manual_off_time']:
                    off_duration = (now - light_timer['manual_off_time']).total_seconds()
                    light_timer['remaining_extension'] += off_duration
                    light_timer['manual_off_time'] = None

    return render_template('view_control.html', state=state)

if __name__ == "__main__":
    threading.Thread(target=control_loop, daemon=True).start()
    threading.Thread(target=status_log_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=9000, debug=True)

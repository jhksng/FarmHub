import time
import threading
from datetime import datetime, timedelta
from flask import Flask, request, render_template, render_template_string
import mysql.connector

# RPi.GPIO 라이브러리 임포트 (가상 모드 포함)
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    print("RPi.GPIO 라이브러리를 찾을 수 없습니다. GPIO 제어는 비활성화됩니다.")
    GPIO_AVAILABLE = False
    class DummyGPIO:
        def setmode(self, mode): pass
        def setup(self, pin, mode, initial=None): pass
        def output(self, pin, value): print(f"DUMMY GPIO: Pin {pin} -> {value}")
        def cleanup(self): pass
        BCM = 11; OUT = 0; LOW = 0; HIGH = 1
    GPIO = DummyGPIO()

app = Flask(__name__)

# --- 설정 변수 ---
pins = { 'LED': 5, 'CoolerA': 6, 'CoolerB': 13, 'WaterPump': 19, 'PTC': 26 }
pin_map_rev = {v: k for k, v in pins.items()}

# --- 상태 관리 변수 ---
device_state = {pin: GPIO.HIGH for pin in pins.values()}
manual_override = {name: False for name in pins.keys()}
current_loop_thread = None
current_crop_name = None
stop_event = threading.Event()

# --- GPIO 초기화 ---
if GPIO_AVAILABLE:
    GPIO.setmode(GPIO.BCM)
    for pin_num in pins.values():
        GPIO.setup(pin_num, GPIO.OUT, initial=GPIO.HIGH)
    print("GPIO 핀 초기 설정 완료.")

# --- 데이터베이스 함수 ---
def get_db_connection():
    return mysql.connector.connect(host="localhost", user="root", password="1234", database="sensor")

def load_crop_settings(crop_name):
    db = get_db_connection(); cursor = db.cursor()
    cursor.execute("SELECT target_temp, target_humi, target_light, target_soil FROM crop_info WHERE crop = %s", (crop_name,))
    result = cursor.fetchone()
    cursor.close(); db.close()
    if result: return {'temp': result[0], 'humi': result[1], 'light_duration': result[2], 'soil': result[3]}
    return None

def get_latest_sensor_values(crop_name):
    db = get_db_connection(); cursor = db.cursor()
    cursor.execute("SELECT id FROM crop_info WHERE crop = %s", (crop_name,)); crop_id_res = cursor.fetchone()
    if not crop_id_res: cursor.close(); db.close(); return None
    crop_id = crop_id_res[0]
    cursor.execute("SELECT temp, humi, soil, timestamp FROM sensor_log WHERE crop_id = %s ORDER BY timestamp DESC LIMIT 1", (crop_id,))
    result = cursor.fetchone()
    cursor.close(); db.close()
    if result: return {'temp': result[0], 'humi': result[1], 'soil': result[2], 'timestamp': result[3]}
    return None

# --- 장치 제어 함수 ---
def control_device(name, value):
    pin_num = pins[name]
    if device_state[pin_num] != value:
        device_state[pin_num] = value
        GPIO.output(pin_num, value)
        action = "켜짐 (LOW)" if value == GPIO.LOW else "꺼짐 (HIGH)"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {name} 제어: {action}")

def water_pump_routine():
    print("워터펌프 작동 시작")
    control_device('WaterPump', GPIO.LOW)
    time.sleep(10)
    control_device('WaterPump', GPIO.HIGH)
    print("워터펌프 작동 종료")

def heater_routine():
    print("히터 작동 시작")
    control_device('PTC', GPIO.LOW)
    time.sleep(60)
    control_device('PTC', GPIO.HIGH)
    print("히터 작동 종료")

# --- 자동 제어 루프 ---
def start_control_loop(crop_name, stop_event):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] '{crop_name}' 작물 제어 루프 시작됨.")
    last_water_time = datetime.min
    last_heat_time = datetime.min
    
    while not stop_event.is_set():
        time.sleep(10)
        now = datetime.now()
        
        db = get_db_connection(); cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT selected_crop, selected_time FROM users LIMIT 1")
        user_selection = cursor.fetchone()
        cursor.execute("SELECT * FROM control_state LIMIT 1")
        control_state_data = cursor.fetchone()
        cursor.close(); db.close()

        if not user_selection or user_selection['selected_crop'] != crop_name:
            break

        crop_settings = load_crop_settings(crop_name)
        sensor = get_latest_sensor_values(crop_name)
        if not crop_settings or not sensor: continue

        # --- 생장등 제어 ---
        if not manual_override['LED']:
            target_light_hours = crop_settings['light_duration']
            target_light_seconds = target_light_hours * 3600
            
            cycle_start_time = user_selection['selected_time']
            acc_seconds = control_state_data['light_on_seconds_acc']
            last_update_time = control_state_data['light_last_update_time']
            
            if cycle_start_time and (now - cycle_start_time).total_seconds() >= 86400:
                print("하루 주기 완료. LED 타이머를 리셋합니다.")
                db_update = get_db_connection(); cursor_update = db_update.cursor()
                cursor_update.execute("UPDATE users SET selected_time = %s LIMIT 1", (now,))
                cursor_update.execute("UPDATE control_state SET light_on_seconds_acc = 0, light_last_update_time = %s LIMIT 1", (now,))
                db_update.commit(); cursor_update.close(); db_update.close()
                acc_seconds = 0; last_update_time = now

            current_on_time = acc_seconds
            if device_state[pins['LED']] == GPIO.LOW and last_update_time:
                current_on_time += (now - last_update_time).total_seconds()

            if current_on_time < target_light_seconds:
                if device_state[pins['LED']] == GPIO.HIGH:
                    control_device('LED', GPIO.LOW)
                    db_update = get_db_connection(); cursor_update = db_update.cursor()
                    cursor_update.execute("UPDATE control_state SET light_last_update_time = %s LIMIT 1", (now,))
                    db_update.commit(); cursor_update.close(); db_update.close()
                print(f"LED ON. 목표 {target_light_hours}시간 중 {timedelta(seconds=int(current_on_time))} 만큼 채움.")
            else:
                if device_state[pins['LED']] == GPIO.LOW:
                    final_acc_seconds = acc_seconds + (now - last_update_time).total_seconds()
                    control_device('LED', GPIO.HIGH)
                    db_update = get_db_connection(); cursor_update = db_update.cursor()
                    cursor_update.execute("UPDATE control_state SET light_on_seconds_acc = %s, light_last_update_time = %s LIMIT 1", (final_acc_seconds, now))
                    db_update.commit(); cursor_update.close(); db_update.close()
                print(f"LED 목표 시간({target_light_hours}시간) 달성. OFF 유지.")

        # --- 워터펌프, 히터, 쿨러 제어 ---
        if not manual_override['WaterPump'] and sensor['soil'] < crop_settings['soil'] and (now - last_water_time).total_seconds() >= 600:
            threading.Thread(target=water_pump_routine).start()
            last_water_time = now
        
        if not manual_override['PTC'] and sensor['temp'] < crop_settings['temp'] - 2 and (now-last_heat_time).total_seconds() >=600:
            threading.Thread(target=heater_routine).start()
            last_heat_time = now
            
        if not manual_override['CoolerA'] and sensor['temp'] > crop_settings['temp'] + 2:
            control_device('CoolerA', GPIO.LOW); control_device('CoolerB', GPIO.LOW)
        elif not manual_override['CoolerA']:
            control_device('CoolerA', GPIO.HIGH); control_device('CoolerB', GPIO.HIGH)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] '{crop_name}' 제어 루프 정상적으로 종료됨.")

# --- 웹 인터페이스 ---
@app.route('/select')

@app.route('/')
	
@app.route('/start_auto', methods=['GET', 'POST'])
def start_auto():
    global current_loop_thread, current_crop_name, stop_event
    if request.method == 'GET':
        return render_template_string('''<!doctype html><html lang="ko"><head><meta charset="UTF-8"><title>작물 제어 시작</title><style>body{font-family:Arial,sans-serif;margin:20px;background-color:#f4f4f4;color:#333}h2{color:#0056b3}form{background-color:#fff;padding:25px;border-radius:8px;display:inline-block}input[type=text],input[type=submit]{padding:10px 15px;margin:8px 0;display:block;border:1px solid #ddd;border-radius:4px;width:100%}input[type=submit]{background-color:#28a745;color:#fff;cursor:pointer;font-weight:700}</style></head><body><h2>작물 이름을 입력하세요</h2><form action="/start_auto" method="post"><input type="text" name="crop" placeholder="예: Apple" required><input type="submit" value="자동 제어 시작"></form></body></html>''')
    
    crop_name = request.form['crop'].strip()
    db = get_db_connection(); cursor = db.cursor()
    cursor.execute("SELECT crop FROM crop_info WHERE crop = %s", (crop_name,))
    if not cursor.fetchone(): return "오류: 유효한 작물이 아닙니다."

    if current_loop_thread and current_loop_thread.is_alive():
        stop_event.set(); current_loop_thread.join(timeout=5)

    now_time = datetime.now()
    cursor.execute("UPDATE users SET selected_crop=%s, selected_time=%s LIMIT 1", (crop_name, now_time))
    cursor.execute("UPDATE control_state SET light_on_seconds_acc=0, light_last_update_time=%s LIMIT 1", (now_time,))
    db.commit()

    stop_event = threading.Event()
    current_crop_name = crop_name
    current_loop_thread = threading.Thread(target=start_control_loop, args=(crop_name, stop_event), daemon=True)
    current_loop_thread.start()
    
    return f"<h1>{crop_name} 자동 제어를 시작합니다.</h1><p><a href='/control'>수동 제어 페이지로 가기</a></p>"

@app.route('/control')
def control_page():
    return render_template('view_control.html', device_state=device_state, manual_override=manual_override, pins=pins)

@app.route('/controller', methods=["POST"])
def controller():
    now = datetime.now()
    db_conn = get_db_connection(); cursor = db_conn.cursor(dictionary=True)
    
    for pin_str, value_str in request.form.items():
        pin_num = int(pin_str)
        new_state = int(value_str)
        device_name = pin_map_rev[pin_num]

        if device_state[pin_num] != new_state:
            manual_override[device_name] = True
            
            if device_name == 'LED':
                cursor.execute("SELECT light_on_seconds_acc, light_last_update_time FROM control_state LIMIT 1")
                led_timer_data = cursor.fetchone()
                acc_seconds = led_timer_data['light_on_seconds_acc'] or 0
                last_update = led_timer_data['light_last_update_time']
                
                if new_state == GPIO.HIGH: # 수동 OFF
                    if last_update: acc_seconds += (now - last_update).total_seconds()
                    cursor.execute("UPDATE control_state SET light_on_seconds_acc = %s, light_last_update_time = %s LIMIT 1", (acc_seconds, now))
                else: # 수동 ON
                    cursor.execute("UPDATE control_state SET light_last_update_time = %s LIMIT 1", (now,))
            
            control_device(device_name, new_state)

    db_conn.commit(); cursor.close(); db_conn.close()
    return ('', 204)

@app.route('/auto_mode/<string:device_name>', methods=['POST'])
def set_auto_mode(device_name):
    manual_override[device_name] = False
    
    if device_name == 'LED':
        db_conn = get_db_connection(); cursor = db_conn.cursor()
        cursor.execute("UPDATE control_state SET light_last_update_time = %s LIMIT 1", (datetime.now(),))
        db_conn.commit(); cursor.close(); db_conn.close()
    
    print(f"{device_name}을(를) 자동 모드로 전환합니다.")
    return ('', 204)

if __name__=="__main__":
    try:
        app.run(host='0.0.0.0', port=9000, debug=False)
    finally:
        if GPIO_AVAILABLE:
            print("애플리케이션 종료 시 GPIO.cleanup() 실행")
            GPIO.cleanup()

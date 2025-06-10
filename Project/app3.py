import time
import threading
from datetime import datetime, timedelta
from flask import Flask, request
import mysql.connector
import os

# --- 라우트(Blueprint) 파일에서 Blueprint 객체들을 가져옵니다 ---
# 각 파일이 해당 이름의 Blueprint 객체(예: main_bp)를 가지고 있어야 합니다.
from routes.main_routes import main_bp
from routes.control_routes import control_bp
# from routes.camera_routes import camera_bp  # 나중에 기능을 만들면 주석 해제
# from routes.ai_routes import ai_bp        # 나중에 기능을 만들면 주석 해제


# --- RPi.GPIO 라이브러리 임포트 (가상 모드 포함) ---
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


# ==============================================================================
# 1. Flask 앱 생성 및 기본 설정
# ==============================================================================
app = Flask(__name__)
# 세션을 사용하기 위한 시크릿 키 (flash 메시지 등에 필요)
app.secret_key = os.environ.get("SECRET_KEY", "your_unique_and_secret_key")


# ==============================================================================
# 2. 전역 설정 및 상태 변수 (시스템의 모든 상태를 여기서 관리)
# ==============================================================================
pins = { 'LED': 5, 'CoolerA': 6, 'CoolerB': 13, 'WaterPump': 19, 'PTC': 26 }
pin_map_rev = {v: k for k, v in pins.items()}

# 장치의 현재 물리적 상태 (ON=LOW=0, OFF=HIGH=1)
device_state = {pin: GPIO.HIGH for pin in pins.values()}
# 수동 제어 모드 플래그 (True이면 자동 제어가 해당 장치를 건너뜀)
manual_override = {name: False for name in pins.keys()}

# 자동 제어 스레드 관리를 위한 전역 변수
current_loop_thread = None
current_crop_name = None
stop_event = threading.Event()


# ==============================================================================
# 3. 하드웨어 및 데이터베이스 핵심 함수
# ==============================================================================

# --- GPIO 초기화 ---
if GPIO_AVAILABLE:
    GPIO.setmode(GPIO.BCM)
    for pin_num in pins.values():
        GPIO.setup(pin_num, GPIO.OUT, initial=GPIO.HIGH)
    print("GPIO 핀 초기 설정 완료.")

# --- 데이터베이스 연결 함수 ---
def get_db_connection():
    # 이 함수는 프로젝트 전체에서 DB에 연결할 때 사용됩니다.
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="1234",
        database="sensor"
    )

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
        
        try:
            db = get_db_connection(); cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT selected_crop, selected_time FROM users LIMIT 1")
            user_selection = cursor.fetchone()
            cursor.execute("SELECT * FROM control_state LIMIT 1")
            control_state_data = cursor.fetchone()
            cursor.close(); db.close()

            if not user_selection or user_selection['selected_crop'] != crop_name:
                print(f"작물 변경 감지. '{crop_name}' 루프를 종료합니다.")
                break

            db_settings = get_db_connection(); cursor_settings = db_settings.cursor()
            cursor_settings.execute("SELECT target_temp, target_humi, target_light, target_soil FROM crop_info WHERE crop = %s", (crop_name,))
            settings_res = cursor_settings.fetchone()
            cursor_settings.close(); db_settings.close()
            if not settings_res: continue
            crop_settings = {'temp': settings_res[0], 'humi': settings_res[1], 'light_duration': settings_res[2], 'soil': settings_res[3]}
            
            db_sensor = get_db_connection(); cursor_sensor = db_sensor.cursor()
            cursor_sensor.execute("SELECT id FROM crop_info WHERE crop = %s", (crop_name,)); crop_id_res = cursor_sensor.fetchone()
            if not crop_id_res: cursor_sensor.close(); db_sensor.close(); continue
            crop_id = crop_id_res[0]
            cursor_sensor.execute("SELECT temp, humi, soil, timestamp FROM sensor_log WHERE crop_id = %s ORDER BY timestamp DESC LIMIT 1", (crop_id,))
            sensor_res = cursor_sensor.fetchone()
            cursor_sensor.close(); db_sensor.close()
            if not sensor_res: continue
            sensor = {'temp': sensor_res[0], 'humi': sensor_res[1], 'soil': sensor_res[2], 'timestamp': sensor_res[3]}


            # --- 생장등 제어 로직 ---
            if not manual_override['LED']:
                target_light_hours = crop_settings['light_duration']
                target_light_seconds = target_light_hours * 3600
                
                cycle_start_time = user_selection['selected_time']
                acc_seconds = control_state_data['light_on_seconds_acc'] if control_state_data['light_on_seconds_acc'] else 0
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

            # --- 워터펌프, 히터, 쿨러 제어 로직 ---
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

        except mysql.connector.Error as err:
            print(f"자동 제어 루프 DB 오류: {err}")
        except Exception as e:
            print(f"자동 제어 루프 알 수 없는 오류: {e}")

    print(f"[{datetime.now().strftime('%H:%M:%S')}] '{crop_name}' 제어 루프 정상적으로 종료됨.")


# ==============================================================================
# 4. 앱 컨텍스트에 핵심 자원 등록 (Blueprint와 공유하기 위함)
# ==============================================================================
# 다른 파일(Blueprint)에서 current_app.pins 등으로 이 변수들에 접근할 수 있습니다.
app.pins = pins
app.device_state = device_state
app.manual_override = manual_override
app.current_loop_thread = current_loop_thread
app.current_crop_name = current_crop_name
app.stop_event = stop_event
app.start_control_loop = start_control_loop
app.get_db_connection = get_db_connection


# ==============================================================================
# 5. 수동 제어 API 엔드포인트
# ==============================================================================
# JavaScript(fetch)의 요청을 직접 처리하는 백엔드 API
@app.route('/controller', methods=["POST"])
def controller():
    now = datetime.now()
    try:
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
                        cursor.execute("UPDATE control_state SET light_on_seconds_acc = %s, light_last_update_time = %s LIMIT 1", (int(acc_seconds), now))
                    else: # 수동 ON
                        cursor.execute("UPDATE control_state SET light_last_update_time = %s LIMIT 1", (now,))
                
                control_device(device_name, new_state)

        db_conn.commit(); cursor.close(); db_conn.close()
    except Exception as e:
        print(f"컨트롤러 오류: {e}")
    return ('', 204)

@app.route('/auto_mode/<string:device_name>', methods=['POST'])
def set_auto_mode(device_name):
    manual_override[device_name] = False
    
    if device_name == 'LED':
        try:
            db_conn = get_db_connection(); cursor = db_conn.cursor()
            cursor.execute("UPDATE control_state SET light_last_update_time = %s LIMIT 1", (datetime.now(),))
            db_conn.commit(); cursor.close(); db_conn.close()
        except Exception as e:
            print(f"자동 모드 전환 오류: {e}")

    print(f"{device_name}을(를) 자동 모드로 전환합니다.")
    return ('', 204)


# ==============================================================================
# 6. Blueprint 등록
# ==============================================================================
app.register_blueprint(main_bp)
app.register_blueprint(control_bp)
# app.register_blueprint(camera_bp) # 나중에 추가
# app.register_blueprint(ai_bp)       # 나중에 추가


# ==============================================================================
# 7. 앱 실행
# ==============================================================================
if __name__ == "__main__":
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    finally:
        if GPIO_AVAILABLE:
            print("애플리케이션 종료 시 GPIO.cleanup() 실행")
            GPIO.cleanup()


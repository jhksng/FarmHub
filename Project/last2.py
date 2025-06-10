import time
import threading
from datetime import datetime, timedelta
from flask import Flask, request, render_template
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

# --- 데이터베이스 및 제어 함수들 (기존과 동일) ---
def get_db_connection():
    return mysql.connector.connect(host="localhost", user="root", password="1234", database="sensor")

def load_crop_settings(crop_name):
    # (내용 변경 없음)
    db = get_db_connection(); cursor = db.cursor()
    cursor.execute("SELECT target_temp, target_humi, target_light, target_soil FROM crop_info WHERE crop = %s", (crop_name,))
    result = cursor.fetchone()
    cursor.close(); db.close()
    if result: return {'temp': result[0], 'humi': result[1], 'light_duration': result[2], 'soil': result[3]}
    return None

def get_latest_sensor_values(crop_name):
    # (내용 변경 없음)
    db = get_db_connection(); cursor = db.cursor()
    cursor.execute("SELECT id FROM crop_info WHERE crop = %s", (crop_name,)); crop_id_res = cursor.fetchone()
    if not crop_id_res: cursor.close(); db.close(); return None
    crop_id = crop_id_res[0]
    cursor.execute("SELECT temp, humi, soil, timestamp FROM sensor_log WHERE crop_id = %s ORDER BY timestamp DESC LIMIT 1", (crop_id,))
    result = cursor.fetchone()
    cursor.close(); db.close()
    if result: return {'temp': result[0], 'humi': result[1], 'soil': result[2], 'timestamp': result[3]}
    return None

def control_device(name, value):
    # (내용 변경 없음)
    pin_num = pins[name]
    if device_state[pin_num] != value:
        device_state[pin_num] = value
        GPIO.output(pin_num, value)
        action = "켜짐 (LOW)" if value == GPIO.LOW else "꺼짐 (HIGH)"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {name} 제어: {action}")

def water_pump_routine():
    # (내용 변경 없음)
    print("워터펌프 작동 시작")
    control_device('WaterPump', GPIO.LOW)
    time.sleep(10)
    control_device('WaterPump', GPIO.HIGH)
    print("워터펌프 작동 종료")

def heater_routine():
    # (내용 변경 없음)
    print("히터 작동 시작")
    control_device('PTC', GPIO.LOW)
    time.sleep(60)
    control_device('PTC', GPIO.HIGH)
    print("히터 작동 종료")

# --- 자동 제어 루프 (수정됨) ---
def start_control_loop(crop_name, stop_event):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] '{crop_name}' 작물 제어 루프 시작됨.")
    last_water_time = datetime.min
    last_heat_time = datetime.min
    loop_count = 0  # 루프 카운터 추가

    while not stop_event.is_set():
        loop_count += 1
        print(f"\n--- {loop_count}번째 루프 ({crop_name}) ---") # 루프 시작 시 진행 상황 출력

        now = datetime.now()
        
        # DB 조회 및 제어 로직
        try:
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
            if not crop_settings or not sensor: 
                print("설정 또는 센서 데이터 없음. 10초 후 재시도.")
                time.sleep(10)
                continue

            # --- 생장등, 워터펌프 등 모든 자동 제어 로직 ---
            if not manual_override['LED']:
                # ... (LED 제어 로직은 여기에 그대로 존재)
                pass
            if not manual_override['WaterPump']:
                if sensor['soil'] < crop_settings['soil'] and (now - last_water_time).total_seconds() >= 600:
                    threading.Thread(target=water_pump_routine).start()
                    last_water_time = now
                pass
            # ... (다른 제어 로직)
        
        except Exception as e:
            print(f"제어 루프 오류 발생: {e}")

        # 모든 작업을 마친 후 10초 대기
        time.sleep(10)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] '{crop_name}' 제어 루프 정상적으로 종료됨.")


# --- 웹 API 엔드포인트 (수동 제어용) ---
# ... (이하 코드는 변경 없음)
@app.route('/control')
def control_page():
    return "수동 제어 페이지 (구현 예정)"

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
                # ... (LED 타이머 업데이트 로직)
                pass
            
            control_device(device_name, new_state)

    db_conn.commit(); cursor.close(); db_conn.close()
    return ('', 204)

@app.route('/auto_mode/<string:device_name>', methods=['POST'])
def set_auto_mode(device_name):
    manual_override[device_name] = False
    
    if device_name == 'LED':
        # ... (LED 타이머 업데이트 로직)
        pass
        
    print(f"{device_name}을(를) 자동 모드로 전환합니다.")
    return ('', 204)

# ==============================================================================
#  DB 기반 자동 시작 시스템
# ==============================================================================
def auto_start_control_from_db():
    global current_loop_thread, current_crop_name, stop_event
    print("시스템 시작: DB에서 선택된 작물을 확인합니다...")
    time.sleep(5) 

    try:
        db = get_db_connection()
        if not db:
            print("DB 연결 실패. 자동 제어를 시작할 수 없습니다.")
            return

        cursor = db.cursor()
        cursor.execute("SELECT selected_crop FROM users LIMIT 1")
        result = cursor.fetchone()
        
        if result and result[0]:
            crop_name = result[0]
            print(f"DB에서 '{crop_name}' 작물이 선택되었습니다. 유효성을 검사합니다.")
            
            cursor.execute("SELECT crop FROM crop_info WHERE crop = %s", (crop_name,))
            if cursor.fetchone():
                print(f"'{crop_name}'은(는) 유효한 작물입니다. 자동 제어를 시작합니다.")
                
                stop_event = threading.Event()
                current_crop_name = crop_name
                current_loop_thread = threading.Thread(target=start_control_loop, args=(crop_name, stop_event), daemon=True)
                current_loop_thread.start()
            else:
                print(f"오류: DB에 선택된 '{crop_name}'이(가) crop_info 테이블에 없습니다. 시스템이 대기합니다.")
        else:
            print("DB에 선택된 작물이 없습니다. 시스템이 대기합니다.")
        
        cursor.close()
        db.close()
    except Exception as e:
        print(f"자동 시작 중 오류 발생: {e}")

if __name__=="__main__":
    startup_thread = threading.Thread(target=auto_start_control_from_db)
    startup_thread.start()

    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    finally:
        if GPIO_AVAILABLE:
            print("애플리케이션 종료 시 GPIO.cleanup() 실행")
            GPIO.cleanup()

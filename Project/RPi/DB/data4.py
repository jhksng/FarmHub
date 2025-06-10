import serial
import mysql.connector
import time
from datetime import datetime, date, timedelta
import sys # sys 모듈 추가

# 라즈베리파이 하드웨어 제어 및 센서 라이브러리 import
import board
import adafruit_sht31d

# --- I2C 및 센서 초기화 (글로벌 변수로 선언) ---
try:
    i2c = board.I2C()
    sensor = adafruit_sht31d.SHT31D(i2c, address=0x44)
    print("✅ I2C 센서 초기화 완료.")
    sys.stdout.flush() # 즉시 출력
except Exception as e:
    print(f"❌ I2C 센서 초기화 오류: {e}")
    sys.stdout.flush()
    # exit(1)

# --- 아두이노 시리얼 연결 (글로벌 변수로 선언) ---
try:
    arduino = serial.Serial('/dev/ttyACM0', 9600, timeout=5) # timeout을 넉넉하게 설정
    time.sleep(2) # 아두이노 초기화 시간 대기
    print("✅ 아두이노 시리얼 연결 완료.")
    sys.stdout.flush()
except serial.SerialException as e:
    print(f"❌ 아두이노 시리얼 연결 오류: {e}")
    sys.stdout.flush()
    # exit(1)


def get_user_crop_and_time(username_to_fetch):
    # ... (이 함수는 변경 없음) ...
    db = None
    cursor = None
    try:
        db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="1234",
            database="sensor"
        )
        cursor = db.cursor()
        query = "SELECT selected_crop, selected_time FROM users WHERE username = %s LIMIT 1"
        cursor.execute(query, (username_to_fetch,))

        result = cursor.fetchone()
        if result:
            return {'selected_crop_name': result[0], 'selected_time': result[1]}
        else:
            print(f"⚠️ 사용자 '{username_to_fetch}'의 작물 또는 선택 시간을 찾을 수 없습니다.")
            sys.stdout.flush()
            return None

    except mysql.connector.Error as err:
        print(f"❌ DB 오류 발생 (get_user_crop_and_time): {err}")
        sys.stdout.flush()
        return None

    finally:
        try:
            if cursor:
                cursor.close()
            if db and db.is_connected():
                db.close()
        except Exception as e:
            print(f"❌ DB 연결 닫기 오류: {e}")
            sys.stdout.flush()


def get_crop_info_by_name(crop_name):
    # ... (이 함수는 변경 없음) ...
    db = None
    cursor = None
    try:
        db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="1234",
            database="sensor"
        )
        cursor = db.cursor()
        query = "SELECT id, crop, target_light, target_growth FROM crop_info WHERE crop = %s LIMIT 1"
        cursor.execute(query, (crop_name,))

        result = cursor.fetchone()
        if result:
            return {
                'id': result[0],
                'name': result[1],
                'target_light': float(result[2]),
                'target_growth': float(result[3])
            }
        else:
            print(f"⚠️ '{crop_name}' 작물을 crop_info 테이블에서 찾을 수 없습니다.")
            sys.stdout.flush()
            return None

    except mysql.connector.Error as err:
        print(f"❌ DB 오류 발생 (get_crop_info_by_name): {err}")
        sys.stdout.flush()
        return None

    finally:
        try:
            if cursor:
                cursor.close()
            if db and db.is_connected():
                db.close()
        except Exception as e:
            print(f"❌ DB 연결 닫기 오류: {e}")
            sys.stdout.flush()


def getTemp(sensor_obj):
    try:
        return float(sensor_obj.temperature)
    except Exception as e:
        print(f"🚫 온도 센서 읽기 오류: {e}")
        sys.stdout.flush()
        return 0.0

def getHumi(sensor_obj):
    try:
        return float(sensor_obj.relative_humidity)
    except Exception as e:
        print(f"🚫 습도 센서 읽기 오류: {e}")
        sys.stdout.flush()
        return 0.0


def collect_and_save_sensor_data():
    if 'arduino' not in globals() or not arduino.is_open:
        print("❌ 아두이노 시리얼이 연결되지 않았습니다. 작업 중단.")
        sys.stdout.flush()
        return
    if 'sensor' not in globals() or sensor is None:
        print("❌ SHT31D 센서가 초기화되지 않았습니다. 작업 중단.")
        sys.stdout.flush()
        return

    user_data = get_user_crop_and_time(username_to_fetch="admin")
    if not user_data:
        print("사용자 정보나 선택된 작물이 없어 센서 데이터 수집을 시작할 수 없습니다.")
        sys.stdout.flush()
        return

    selected_crop_name = user_data['selected_crop_name']
    selected_time = user_data['selected_time']

    if not selected_crop_name or not selected_time:
        print("선택된 작물 또는 선택 시간이 유효하지 않아 센서 데이터 수집을 시작할 수 없습니다.")
        sys.stdout.flush()
        return

    crop_info = get_crop_info_by_name(selected_crop_name)
    if not crop_info:
        print(f"선택된 작물 '{selected_crop_name}'에 대한 정보를 찾을 수 없어 센서 데이터 수집을 시작할 수 없습니다.")
        sys.stdout.flush()
        return

    crop_id = crop_info['id']
    crop_name_for_log = crop_info['name']
    target_light_hours = float(crop_info.get('target_light', 0.0))
    harvest_days = float(crop_info.get('target_growth', 1.0))


    soil_values = []
    water_values = []
    temp_values = []
    humi_values = []

    print(f"\n🌱 '{crop_name_for_log}' 작물의 센서 데이터 수집을 시작합니다. (1분간 10초 간격 6회)")
    print(f"   재배 시작 시각: {selected_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   작물 목표: 하루 일조량 {target_light_hours}시간, 수확까지 {harvest_days}일")
    sys.stdout.flush()

    for i in range(6):
        try:
            # 입력 버퍼를 확실히 비웁니다.
            arduino.reset_input_buffer()
            # 아두이노가 데이터를 보낼 시간을 충분히 줍니다.
            time.sleep(0.5) # 0.1초에서 0.5초로 늘려보세요.

            if arduino.in_waiting > 0:
                data = arduino.readline().decode('utf-8').strip()
                print(f"DEBUG: 수신 데이터: '{data}'") # 디버그용 출력
                sys.stdout.flush()

                values = data.split(",")

                if len(values) >= 2: # soil, water만 있다고 가정
                    try:
                        soil = float(values[0].strip())
                        water = float(values[1].strip())

                        temp = round(getTemp(sensor), 2)
                        humi = round(getHumi(sensor), 2)

                        soil_values.append(soil)
                        water_values.append(water)
                        temp_values.append(temp)
                        humi_values.append(humi)

                        print(f"📥 {i+1}/6 수집: Soil={soil:.2f}, Water={water:.2f}, Temp={temp:.2f}, Humi={humi:.2f}")
                        sys.stdout.flush()
                    except ValueError:
                        print(f"🚫 데이터 변환 오류: '{data}' - 숫자 형식 확인 필요.")
                        sys.stdout.flush()
                else:
                    print(f"🚫 잘못된 데이터 형식: '{data}' (기대: soil,water)")
                    sys.stdout.flush()
            else:
                print(f"⚠️ {i+1}/6 수집: 아두이노 데이터 수신 대기 중... (버퍼 비어있음)")
                sys.stdout.flush()

        except Exception as e:
            print(f"🚫 센서 데이터 읽기/파싱 중 예상치 못한 오류: {e}")
            sys.stdout.flush()

        time.sleep(10)

    if soil_values and water_values and temp_values and humi_values:
        avg_soil = round(sum(soil_values) / len(soil_values), 2)
        avg_water = round(sum(water_values) / len(water_values), 2)
        avg_temp = round(sum(temp_values) / len(temp_values), 2)
        avg_humi = round(sum(humi_values) / len(humi_values), 2)

        light_value_for_db = 0.0

        current_time_korea = datetime.now()
        today = current_time_korea.date()
        start_date = selected_time.date()
        elapsed_days = (today - start_date).days

        growth = min(1.0, elapsed_days / harvest_days) if harvest_days > 0 else 0.0

        timestamp = current_time_korea

        try:
            db = mysql.connector.connect(
                host="localhost",
                user="root",
                password="1234",
                database="sensor"
            )
            cursor = db.cursor()
            query = """
                INSERT INTO sensor_log (crop_id, temp, humi, soil, timestamp, light, water, growth)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (crop_id, avg_temp, avg_humi, avg_soil, timestamp, light_value_for_db, avg_water, growth))
            db.commit()
            cursor.close()
            db.close()

            print(f"\n✅ [{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] '{crop_name_for_log}' (ID: {crop_id}) 작물의 센서 데이터 저장 완료")
            print(f"   **생장률**: {growth:.2f} (경과 {elapsed_days}일 / 목표 {harvest_days}일)")
            print(f"   **light 컬럼**: {light_value_for_db:.2f} (아두이노에서 조도값 수신 불가)")
            sys.stdout.flush()

        except Exception as e:
            print(f"❌ DB 저장 오류: {e}")
            sys.stdout.flush()
    else:
        print("⚠️ 수집된 센서 데이터가 충분하지 않습니다. DB에 저장하지 않았습니다. 센서 연결 또는 아두이노 응답을 확인하세요.")
        sys.stdout.flush()


if __name__ == "__main__":
    try:
        collect_and_save_sensor_data()
    finally:
        print("\n📦 프로그램 종료됨.")
        sys.stdout.flush()
        if 'arduino' in globals() and arduino.is_open:
            arduino.close()
            print("아두이노 시리얼 포트 닫힘.")
            sys.stdout.flush()
        else:
            print("아두이노 시리얼 포트가 열려있지 않거나 초기화되지 않아 닫지 않습니다.")
            sys.stdout.flush()

import serial
import mysql.connector
import time
from datetime import datetime, date, timedelta

# 라즈베리파이 하드웨어 제어 및 센서 라이브러리 import
import board # 라즈베리파이 핀 설정용
import adafruit_sht31d # SHT31D 온습도 센서용 (adafruit-circuitpython-sht31d 라이브러리)

# --- I2C 및 센서 초기화 (글로벌 변수로 선언) ---
# 이 부분은 스크립트 시작 시 한 번만 초기화되어야 합니다.
try:
    i2c = board.I2C()
    sensor = adafruit_sht31d.SHT31D(i2c, address=0x44)
    print("✅ I2C 센서 초기화 완료.")
except Exception as e:
    print(f"❌ I2C 센서 초기화 오류: {e}")
    # 센서 초기화 실패 시 스크립트 즉시 종료를 고려할 수 있습니다.
    # exit(1)

# --- 아두이노 시리얼 연결 (글로벌 변수로 선언) ---
try:
    # 매 분 실행 시, 시리얼 포트를 매번 열고 닫아야 하므로 timeout을 충분히 줍니다.
    arduino = serial.Serial('/dev/ttyACM0', 9600, timeout=5) # timeout을 넉넉하게 설정
    time.sleep(2) # 아두이노 초기화 시간 대기
    print("✅ 아두이노 시리얼 연결 완료.")
except serial.SerialException as e:
    print(f"❌ 아두이노 시리얼 연결 오류: {e}")
    # 시리얼 연결 실패 시 스크립트 즉시 종료를 고려할 수 있습니다.
    # exit(1)


def get_user_crop_and_time(username_to_fetch):
    """
    users 테이블에서 특정 사용자의 선택된 작물 이름과 선택 시간을 가져옵니다.
    :param username_to_fetch: 정보를 가져올 사용자의 username.
    :return: {'selected_crop_name': str, 'selected_time': datetime} 또는 None.
    """
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
            return None

    except mysql.connector.Error as err:
        print(f"❌ DB 오류 발생 (get_user_crop_and_time): {err}")
        return None

    finally:
        try:
            if cursor:
                cursor.close()
            if db and db.is_connected():
                db.close()
        except Exception as e:
            print(f"❌ DB 연결 닫기 오류: {e}")


def get_crop_info_by_name(crop_name):
    """
    crop_name을 사용하여 crop_info 테이블에서 작물 ID, 이름, target_light, target_growth 정보를 가져옵니다.
    :param crop_name: 조회할 작물의 이름.
    :return: {'id': int, 'name': str, 'target_light': float, 'target_growth': float} 또는 None.
    """
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
                'target_light': float(result[2]), # 하루 필요한 조도량 (시간)
                'target_growth': float(result[3]) # 수확 가능 일수
            }
        else:
            print(f"⚠️ '{crop_name}' 작물을 crop_info 테이블에서 찾을 수 없습니다.")
            return None

    except mysql.connector.Error as err:
        print(f"❌ DB 오류 발생 (get_crop_info_by_name): {err}")
        return None

    finally:
        try:
            if cursor:
                cursor.close()
            if db and db.is_connected():
                db.close()
        except Exception as e:
            print(f"❌ DB 연결 닫기 오류: {e}")


def getTemp(sensor_obj):
    """SHT31D 센서에서 온도를 읽어옵니다."""
    try:
        return float(sensor_obj.temperature)
    except Exception as e:
        print(f"🚫 온도 센서 읽기 오류: {e}")
        return 0.0 # 오류 발생 시 기본값 반환

def getHumi(sensor_obj):
    """SHT31D 센서에서 습도를 읽어옵니다."""
    try:
        return float(sensor_obj.relative_humidity)
    except Exception as e:
        print(f"🚫 습도 센서 읽기 오류: {e}")
        return 0.0 # 오류 발생 시 기본값 반환


def collect_and_save_sensor_data():
    """
    센서 데이터를 1분 동안 수집(10초 간격 6회), 평균을 계산하여 MySQL 데이터베이스에 저장합니다.
    (크론탭으로 매 분 실행되도록 설계)
    """
    # 전역 변수로 초기화된 아두이노 및 센서 객체가 유효한지 확인
    if 'arduino' not in globals() or not arduino.is_open:
        print("❌ 아두이노 시리얼이 연결되지 않았습니다. 작업 중단.")
        return
    if 'sensor' not in globals() or sensor is None:
        print("❌ SHT31D 센서가 초기화되지 않았습니다. 작업 중단.")
        return

    # --- 사용자 정보 및 선택된 작물/시간 가져오기 ---
    # 중요: 'admin'을 실제 사용자의 username으로 변경해야 합니다.
    user_data = get_user_crop_and_time(username_to_fetch="admin") # <-- 사용자 이름 여기 수정!
    if not user_data:
        print("사용자 정보나 선택된 작물이 없어 센서 데이터 수집을 시작할 수 없습니다.")
        return

    selected_crop_name = user_data['selected_crop_name']
    selected_time = user_data['selected_time'] # datetime 객체로 반환됨

    if not selected_crop_name or not selected_time:
        print("선택된 작물 또는 선택 시간이 유효하지 않아 센서 데이터 수집을 시작할 수 없습니다.")
        return

    # --- 작물별 목표 정보 가져오기 ---
    crop_info = get_crop_info_by_name(selected_crop_name)
    if not crop_info:
        print(f"선택된 작물 '{selected_crop_name}'에 대한 정보를 찾을 수 없어 센서 데이터 수집을 시작할 수 없습니다.")
        return

    crop_id = crop_info['id']
    crop_name_for_log = crop_info['name']
    target_light_hours = float(crop_info.get('target_light', 0.0))
    harvest_days = float(crop_info.get('target_growth', 1.0)) # 0으로 나누는 것 방지


    # --- 센서 값 저장용 리스트 초기화 ---
    soil_values = []
    water_values = []
    temp_values = []
    humi_values = []
    daily_light_duration_values = [] # 아두이노에서 오는 일일 누적 조도 시간 (초 단위)

    print(f"\n🌱 '{crop_name_for_log}' 작물의 센서 데이터 수집을 시작합니다. (1분간 10초 간격 6회)")
    print(f"   재배 시작 시각: {selected_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   작물 목표: 하루 일조량 {target_light_hours}시간, 수확까지 {harvest_days}일")

    # --- 1분 동안 센서 데이터 수집 (10초마다 6회) ---
    for i in range(6):  # 10초마다 6번 = 1분
        try:
            # 시리얼 버퍼 비우기 (오래된 데이터 방지)
            arduino.flushInput()
            # 아두이노가 데이터를 보낼 때까지 잠시 대기
            time.sleep(0.1) # 100ms 대기

            if arduino.in_waiting > 0:
                data = arduino.readline().decode('utf-8').strip()
                # 아두이노 데이터 형식: "soil,water,daily_light_duration_seconds"
                values = data.split(",")

                if len(values) >= 3:
                    try:
                        soil = float(values[0].strip())
                        water = float(values[1].strip())
                        daily_light_duration_seconds = float(values[2].strip())

                        temp = round(getTemp(sensor), 2)
                        humi = round(getHumi(sensor), 2)

                        soil_values.append(soil)
                        water_values.append(water)
                        temp_values.append(temp)
                        humi_values.append(humi)
                        daily_light_duration_values.append(daily_light_duration_seconds)

                        print(f"📥 {i+1}/6 수집: Soil={soil:.2f}, Water={water:.2f}, Temp={temp:.2f}, Humi={humi:.2f}, Daily_Light(s)={daily_light_duration_seconds:.0f}")
                    except ValueError:
                        print(f"🚫 데이터 변환 오류: '{data}' - 숫자 형식 확인 필요.")
                else:
                    print(f"🚫 잘못된 데이터 형식: '{data}' (기대: soil,water,daily_light_duration_seconds)")
            else:
                print(f"⚠️ {i+1}/6 수집: 아두이노 데이터 수신 대기 중...")

        except Exception as e:
            print(f"🚫 센서 데이터 읽기/파싱 중 예상치 못한 오류: {e}")

        time.sleep(10) # 다음 수집까지 10초 대기

    # --- 수집된 데이터가 있을 경우 평균 계산 및 DB 저장 ---
    if soil_values and water_values and temp_values and humi_values and daily_light_duration_values:
        avg_soil = round(sum(soil_values) / len(soil_values), 2)
        avg_water = round(sum(water_values) / len(water_values), 2)
        avg_temp = round(sum(temp_values) / len(temp_values), 2)
        avg_humi = round(sum(humi_values) / len(humi_values), 2)

        # --- light (일일 누적 조도 시간) 계산 ---
        # 1분 동안 받은 '일일 누적 조도 시간' 값들의 평균
        # (아두이노가 하루 동안 동일한 누적 값을 보내는 경우, 첫 번째 값 또는 마지막 값이 더 정확할 수 있습니다)
        light_hours = round(sum(daily_light_duration_values) / len(daily_light_duration_values) / 3600.0, 2)

        # --- growth (생장률) 계산: 선택 시간과 목표 수확일 기준 ---
        current_time_korea = datetime.now()
        today = current_time_korea.date()
        start_date = selected_time.date()
        elapsed_days = (today - start_date).days # 경과된 날짜 수

        growth = min(1.0, elapsed_days / harvest_days) if harvest_days > 0 else 0.0

        timestamp = current_time_korea # 현재 데이터 저장 시점

        # --- MySQL DB 연결 및 데이터 저장 ---
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
            cursor.execute(query, (crop_id, avg_temp, avg_humi, avg_soil, timestamp, light_hours, avg_water, growth))
            db.commit()
            cursor.close()
            db.close()

            print(f"\n✅ [{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] '{crop_name_for_log}' (ID: {crop_id}) 작물의 센서 데이터 저장 완료")
            print(f"   **생장률**: {growth:.2f} (경과 {elapsed_days}일 / 목표 {harvest_days}일)")
            print(f"   **오늘 누적 일조 시간**: {light_hours:.2f} 시간 (목표: {target_light_hours} 시간)")

        except Exception as e:
            print(f"❌ DB 저장 오류: {e}")
    else:
        print("⚠️ 수집된 센서 데이터가 충분하지 않습니다. DB에 저장하지 않았습니다. 센서 연결 또는 아두이노 응답을 확인하세요.")


if __name__ == "__main__":
    try:
        collect_and_save_sensor_data()
    finally:
        print("\n📦 프로그램 종료됨.")
        # 아두이노 시리얼 포트 닫기
        if 'arduino' in globals() and arduino.is_open:
            arduino.close()
            print("아두이노 시리얼 포트 닫힘.")
        else:
            print("아두이노 시리얼 포트가 열려있지 않거나 초기화되지 않아 닫지 않습니다.")

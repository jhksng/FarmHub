import serial
import mysql.connector
import time
from datetime import datetime

# 라즈베리파이 하드웨어 제어 및 센서 라이브러리 import
import board # 라즈베리파이 핀 설정용
import adafruit_sht31d # SHT31D 온습도 센서용 (adafruit-circuitpython-sht31d 라이브러리)

# I2C 및 센서 초기화 (글로벌 변수로 선언)
# 이 부분은 스크립트 시작 시 한 번만 초기화되어야 합니다.
try:
    i2c = board.I2C()
    sensor = adafruit_sht31d.SHT31D(i2c, address=0x44)
    print("✅ I2C 센서 초기화 완료.")
except Exception as e:
    print(f"❌ I2C 센서 초기화 오류: {e}")
    # 센서 초기화 실패 시 스크립트 종료를 고려할 수 있습니다.
    # exit(1) # 필요하다면 스크립트 즉시 종료

# 아두이노 시리얼 연결 (글로벌 변수로 선언)
try:
    arduino = serial.Serial('/dev/ttyACM0', 9600, timeout=1) # timeout 추가로 안정성 향상
    time.sleep(2) # 아두이노 초기화 시간 대기
    print("✅ 아두이노 시리얼 연결 완료.")
except serial.SerialException as e:
    print(f"❌ 아두이노 시리얼 연결 오류: {e}")
    # 시리얼 연결 실패 시 스크립트 종료를 고려할 수 있습니다.
    # exit(1) # 필요하다면 스크립트 즉시 종료


def get_selected_crop():
    try:
        db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="1234",
            database="sensor"
        )
        cursor = db.cursor()
        cursor.execute("SELECT selected_crop FROM users LIMIT 1")

        if cursor.with_rows:
            result = cursor.fetchone()
            return result[0] if result else None
        else:
            print("⚠️ SELECT 문이 결과를 반환하지 않았습니다. (users 테이블)")
            return None

    except mysql.connector.Error as err:
        print(f"❌ DB 오류 발생 (get_selected_crop): {err}")
        return None

    finally:
        try:
            if 'cursor' in locals() and cursor is not None:
                cursor.close()
            if 'db' in locals() and db is not None and db.is_connected():
                db.close()
        except Exception as e:
            print(f"❌ DB 연결 닫기 오류: {e}")


def getTemp(sensor):
    return float(sensor.temperature)

def getHumi(sensor):
    return float(sensor.relative_humidity)


def collect_and_save_sensor_data():
    # 시리얼 포트와 센서가 전역 변수로 이미 초기화되어 있다고 가정합니다.
    # 만약 초기화 실패로 arduino나 sensor 객체가 없다면, 함수 시작 시 다시 확인하거나 오류 처리 필요
    if 'arduino' not in globals() or not arduino.is_open:
        print("❌ 아두이노 시리얼이 연결되지 않았습니다. 작업 중단.")
        return
    if 'sensor' not in globals() or sensor is None:
        print("❌ SHT31D 센서가 초기화되지 않았습니다. 작업 중단.")
        return

    selected_crop = get_selected_crop()
    if not selected_crop:
        print("선택된 작물이 없습니다. 종료합니다.")
        return

    soil_values = []
    water_values = []
    temp_values = []
    humi_values = []

    print(f"🌱 '{selected_crop}' 작물의 센서 데이터를 1분간 수집합니다...")

    for i in range(6):  # 10초마다 6번 = 1분
        try:
            if arduino.in_waiting > 0:
                data = arduino.readline().decode('utf-8').strip()
                values = data.split(",")

                if len(values) >= 2:
                    soil = float(values[0].strip())
                    water = float(values[1].strip())
                    temp = round(getTemp(sensor), 2)
                    humi = round(getHumi(sensor), 2)

                    soil_values.append(soil)
                    water_values.append(water)
                    temp_values.append(temp)
                    humi_values.append(humi)

                    print(f"📥 {i+1}/6 수집: Soil={soil}, Water={water}, Temp={temp}, Humi={humi}")
                else:
                    print("🚫 잘못된 데이터 형식:", data)
            else:
                print(f"⚠️ {i+1}/6 수집: 아두이노 데이터 수신 대기 중...")

        except Exception as e:
            print(f"🚫 데이터 파싱 또는 센서 읽기 오류: {e}")

        time.sleep(10)

    if soil_values:
        avg_soil = round(sum(soil_values) / len(soil_values), 2)
        avg_water = round(sum(water_values) / len(water_values), 2)
        avg_temp = round(sum(temp_values) / len(temp_values), 2)
        avg_humi = round(sum(humi_values) / len(humi_values), 2)
        timestamp = datetime.now()

        try:
            db = mysql.connector.connect(
                host="localhost",
                user="root",
                password="1234",
                database="sensor"
            )
            cursor = db.cursor()
            query = """
                INSERT INTO sensor_log (crop, soil, water, temp, humi, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (selected_crop, avg_soil, avg_water, avg_temp, avg_humi, timestamp))
            db.commit()
            cursor.close()
            db.close()

            print(f"✅ [{timestamp}] 평균 센서 데이터 저장 완료")

        except Exception as e:
            print(f"❌ DB 저장 오류: {e}")
    else:
        print("⚠️ 수집된 센서 데이터가 없습니다. 다시 시도합니다.")


if __name__ == "__main__":
    try:
        collect_and_save_sensor_data()
    finally:
        print("📦 프로그램 종료됨.")
        # 스크립트 시작 시 초기화된 아두이노 시리얼 포트 닫기
        # 'arduino' 변수가 전역 범위에 있고, 성공적으로 열렸을 경우에만 닫습니다.
        if 'arduino' in globals() and arduino.is_open:
            arduino.close()
            print("아두이노 시리얼 포트 닫힘.")
        else:
            print("아두이노 시리얼 포트가 열려있지 않거나 초기화되지 않아 닫지 않습니다.")

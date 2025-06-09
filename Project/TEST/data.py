import serial
import mysql.connector
import time
from datetime import datetime

import board
import adafruit_sht31d

# I2C 및 센서 초기화
i2c = board.I2C()
sensor = adafruit_sht31d.SHT31D(i2c, address=0x44)

# 아두이노 시리얼 연결
arduino = serial.Serial('/dev/ttyACM0', 9600)
time.sleep(2)

# 선택된 작물 이름 가져오기
def get_selected_crop():
    try:
        db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="1234",
            database="sensor"
        )
        cursor = db.cursor()
        cursor.execute("SELECT crop FROM crop_info WHERE selected = 1 LIMIT 1")

        if cursor.with_rows:
            result = cursor.fetchone()
            return result[0] if result else None
        else:
            print("⚠️ SELECT 문이 결과를 반환하지 않았습니다.")
            return None

    except mysql.connector.Error as err:
        print(f"❌ DB 오류 발생: {err}")
        return None

    finally:
        try:
            cursor.close()
            db.close()
        except:
            pass

# 온도 습도 읽기
def getTemp(sensor):
    return float(sensor.temperature)

def getHumi(sensor):
    return float(sensor.relative_humidity)

# 센서 루프
try:
    while True:
        selected_crop = get_selected_crop()
        if not selected_crop:
            print("선택된 작물이 없습니다. 5초 대기...")
            time.sleep(5)
            continue

        if arduino.in_waiting > 0:
            try:
                data = arduino.readline().decode('utf-8').strip()
                values = data.split(",")

                if len(values) < 2:
                    print("🚫 잘못된 데이터 형식:", data)
                    continue

                soil_value = float(values[0].strip())
                water_value = float(values[1].strip())
                temp = round(getTemp(sensor), 2)
                humi = round(getHumi(sensor), 2)
                timestamp = datetime.now()

                # DB 연결
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
                cursor.execute(query, (selected_crop, soil_value, water_value, temp, humi, timestamp))
                db.commit()
                cursor.close()
                db.close()

                print(f"[{timestamp}] '{selected_crop}' → 센서 데이터 저장 완료")

            except Exception as e:
                print(f"데이터 파싱/저장 오류: {e}")

        time.sleep(1)

finally:
    print("📦 프로그램 종료됨.")

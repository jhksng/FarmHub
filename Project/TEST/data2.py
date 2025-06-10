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

        soil_values = []
        water_values = []
        temp_values = []
        humi_values = []

        print(f"🌱 '{selected_crop}' 작물의 센서 데이터를 1분간 수집합니다...")

        for i in range(6):  # 10초마다 6번 = 1분
            if arduino.in_waiting > 0:
                try:
                    data = arduino.readline().decode('utf-8').strip()
                    values = data.split(",")

                    if len(values) < 2:
                        print("🚫 잘못된 데이터 형식:", data)
                        continue

                    soil = float(values[0].strip())
                    water = float(values[1].strip())
                    temp = round(getTemp(sensor), 2)
                    humi = round(getHumi(sensor), 2)

                    soil_values.append(soil)
                    water_values.append(water)
                    temp_values.append(temp)
                    humi_values.append(humi)

                    print(f"📥 {i+1}/6 수집: Soil={soil}, Water={water}, Temp={temp}, Humi={humi}")

                except Exception as e:
                    print(f"🚫 데이터 파싱 오류: {e}")

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

finally:
    print("📦 프로그램 종료됨.")

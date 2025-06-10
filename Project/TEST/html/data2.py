import serial
import mysql.connector
import time
from datetime import datetime

import board
import adafruit_sht31d

# I2C 및 온습도 센서 초기화
i2c = board.I2C()
sensor = adafruit_sht31d.SHT31D(i2c, address=0x44)

# 아두이노 시리얼 연결
arduino = serial.Serial('/dev/ttyACM0', 9600)
time.sleep(2)

# 작물 선택 함수
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

# 온습도 측정
def getTemp(sensor):
    return float(sensor.temperature)

def getHumi(sensor):
    return float(sensor.relative_humidity)

# 루프 시작
try:
    while True:
        selected_crop = get_selected_crop()
        if not selected_crop:
            print("선택된 작물이 없습니다. 5초 대기...")
            time.sleep(5)
            continue

        # 데이터를 담을 리스트
        soil_data = []
        water_data = []
        temp_data = []
        humi_data = []

        print(f"🌱 '{selected_crop}' 작물의 센서 데이터를 수집합니다...")

        for i in range(6):  # 10초 간격, 총 1분
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

                    soil_data.append(soil)
                    water_data.append(water)
                    temp_data.append(temp)
                    humi_data.append(humi)

                    print(f"📥 {i+1}/6 수집: Soil={soil}, Water={water}, Temp={temp}, Humi={humi}")

                except Exception as e:
                    print(f"🚫 데이터 파싱 오류: {e}")

            time.sleep(10)

        # 평균 계산
        if soil_data:
            avg_soil = round(sum(soil_data) / len(soil_data), 2)
            avg_water = round(sum(water_data) / len(water_data), 2)
            avg_temp = round(sum(temp_data) / len(temp_data), 2)
            avg_humi = round(sum(humi_data) / len(humi_data), 2)
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

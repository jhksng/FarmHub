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

# DB 연결
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="1234",
    database="sensor"
)
cursor = db.cursor()

def getTemp(sensor):
    return float(sensor.temperature)

def getHumi(sensor):
    return float(sensor.relative_humidity)

def get_selected_crop():
    cursor.execute("SELECT crop FROM crop_info WHERE selected = 1 LIMIT 1")
    result = cursor.fetchone()
    return result[0] if result else None

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

                soil_value = float(values[0].strip())
                water_value = float(values[1].strip())
                temp = round(getTemp(sensor), 2)
                humi = round(getHumi(sensor), 2)
                timestamp = datetime.now()

                query = """
                    INSERT INTO sensor_log (crop, soil, water, temp, humi, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (selected_crop, soil_value, water_value, temp, humi, timestamp))
                db.commit()

                print(f"[{timestamp}] {selected_crop} → 센서 데이터 저장 완료")

            except Exception as e:
                print(f"데이터 파싱/저장 오류: {e}")

        time.sleep(1)

finally:
    cursor.close()
    db.close()
    print("Database connection closed.")

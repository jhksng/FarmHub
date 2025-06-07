import serial
import mysql.connector
import time
import board
import busio
import adafruit_sht31d
from datetime import datetime

# I2C 초기화 및 센서 객체 생성
try:
    i2c = board.I2C()
    sensor = adafruit_sht31d.SHT31D(i2c, address=0x44)
except Exception as e:
    print(f"❌ 센서 초기화 실패: {e}")
    sensor = None  # 예외 발생 시 None 처리

def getTemp(sensor):
    try:
        return round(float(sensor.temperature), 2)
    except Exception as e:
        print(f"온도 측정 오류: {e}")
        return None

def getHumi(sensor):
    try:
        return round(float(sensor.relative_humidity), 2)
    except Exception as e:
        print(f"습도 측정 오류: {e}")
        return None

# Arduino 연결
try:
    arduino = serial.Serial('/dev/ttyACM0', 9600, timeout=2)
    time.sleep(2)
except Exception as e:
    print(f"❌ 아두이노 연결 실패: {e}")
    exit(1)

# DB 연결
try:
    db = mysql.connector.connect(
        host="localhost", 
        user="root", 
        password="root", 
        database="sensor"
    )
    cursor = db.cursor()
except Exception as e:
    print(f"❌ DB 연결 실패: {e}")
    exit(1)

# 메인 루프
try:
    while True:
        try:
            data = arduino.readline().decode('utf-8').strip()
            print(f"[DEBUG] 수신 데이터: {data}")
            values = data.split(",")

            if len(values) != 2:
                print("⚠️ 데이터 형식 오류, 건너뜀")
                continue

            soil_value = float(values[0].strip())
            water_value = float(values[1].strip())
            timestamp = datetime.now()

            temp = getTemp(sensor)
            humi = getHumi(sensor)

            if temp is None or humi is None:
                print("⚠️ 센서 값 오류, DB 삽입 생략")
                continue

            query = "INSERT INTO sensor_log (soil, water, temp, humi, timestamp) VALUES (%s, %s, %s, %s, %s)"
            cursor.execute(query, (soil_value, water_value, temp, humi, timestamp))
            db.commit()
            print("✅ Data inserted into DB.")

        except Exception as e:
            print(f"❌ 루프 내 오류: {e}")

        time.sleep(1)

except KeyboardInterrupt:
    print("🔌 프로그램 종료 요청됨")

finally:
    cursor.close()
    db.close()
    print("🛑 Database connection closed.")

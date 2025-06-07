import serial
import mysql.connector
import time
from datetime import datetime

# SHT31D 센서용 라이브러리 추가
import board
import adafruit_sht31d

# 온습도 센서 초기화
try:
    i2c = board.I2C()
    sensor = adafruit_sht31d.SHT31D(i2c)
except Exception as e:
    print(f"❌ 온습도 센서 초기화 실패: {e}")
    sensor = None

# 온도 읽기 함수
def get_temperature():
    try:
        return round(sensor.temperature, 2)
    except Exception as e:
        print(f"🌡️ 온도 읽기 오류: {e}")
        return None

# 습도 읽기 함수
def get_humidity():
    try:
        return round(sensor.relative_humidity, 2)
    except Exception as e:
        print(f"💧 습도 읽기 오류: {e}")
        return None

# 아두이노 연결
arduino = serial.Serial('/dev/ttyACM0', 9600)
time.sleep(2)

# MySQL 연결
db = mysql.connector.connect(
    host="localhost", 
    user="root", 
    password="1234", 
    database="sensor"
)
cursor = db.cursor()

try:
    while True:
        if arduino.in_waiting > 0:
            try:
                data = arduino.readline().decode('utf-8').strip()
                values = data.split(",")

                if len(values) != 2:
                    print(f"⚠️ 데이터 형식 오류: {data}")
                    continue

                soil_value = float(values[0].strip())  
                water_value = float(values[1].strip())  
                timestamp = datetime.now()

                # 온습도 측정
                temp = get_temperature()
                humi = get_humidity()

                # 센서 오류 시 건너뜀
                if temp is None or humi is None:
                    print("⚠️ 온습도 센서 오류, 데이터 저장 건너뜀")
                    continue

                # DB 저장
                query = "INSERT INTO sensor_log (soil, water, temp, humi, timestamp) VALUES (%s, %s, %s, %s, %s)"
                cursor.execute(query, (soil_value, water_value, temp, humi, timestamp))
                db.commit()

                print(f"✅ 저장됨 → 토양: {soil_value}, 수위: {water_value}, 온도: {temp}, 습도: {humi}")
            except Exception as e:
                print(f"❌ 파싱 또는 저장 오류: {e}")
        time.sleep(1)

except KeyboardInterrupt:
    print("⛔ 사용자 종료 요청됨")

finally:
    cursor.close()
    db.close()
    print("🛑 데이터베이스 연결 종료됨")

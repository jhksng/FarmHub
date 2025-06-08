import serial
import mysql.connector
import time
from datetime import datetime
# 온습도
import board
import busio
import adafruit_sht31d
i2c = board.I2C()
sensor = adafruit_sht31d.SHT31D(i2c, address=0x44)

# arduino
arduino = serial.Serial('/dev/ttyACM0', 9600)
time.sleep(2)

# sql
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="1234",
    database="sensor"
)
cursor = db.cursor()

# 온도 습도 
def getTemp(sensor):
    return float(sensor.temperature)
def getHumi(sensor):
    return float(sensor.relative_humidity)

# 
soil_data = []
water_data = []
temp_data = []
humi_data = []

try:
    while True:
        for i in range(6):  # 10초 간격으로 센서값 받음
            if arduino.in_waiting > 0:
                try:
                    data = arduino.readline().decode('utf-8').strip()
                    values = data.split(",")
                    soil_value = float(values[0].strip())
                    water_value = float(values[1].strip())
                    # 소수점 둘 째 자리
                    temp = round(getTemp(sensor), 2)
                    humi = round(getHumi(sensor), 2)

                    # 리스트에 저장
                    soil_data.append(soil_value)
                    water_data.append(water_value)
                    temp_data.append(temp)
                    humi_data.append(humi)

                    print(f"Collected: Soil={soil_value}, Water={water_value}, Temp={temp}, Humi={humi}")
                except Exception as e:
                    print(f"ERROR DATA: {e}")
            time.sleep(10)

        # 평균값 계산 및 DB 저장
        if soil_data:
            avg_soil = sum(soil_data) / len(soil_data)
            avg_water = sum(water_data) / len(water_data)
            avg_temp = sum(temp_data) / len(temp_data)
            avg_humi = sum(humi_data) / len(humi_data)
            timestamp = datetime.now()

            try:
                query = "INSERT INTO sensor_log (soil, water, temp, humi, timestamp) VALUES (%s, %s, %s, %s, %s)"
                cursor.execute(query, (avg_soil, avg_water, avg_temp, avg_humi, timestamp))
                db.commit()
                print("INSERT DATA.")
            except Exception as e:
                print(f"DB INSERT ERROR: {e}")

             
            soil_data.clear()
            water_data.clear()
            temp_data.clear()
            humi_data.clear()

finally:
    cursor.close()
    db.close()
    print("Database connection closed.")

import serial
import mysql.connector
import time
from datetime import datetime

import board
import busio
import adafruit_sht31d

i2c = board.I2C()
sensor = adafruit_sht31d.SHT31D(i2c ,address=0x44)


arduino = serial.Serial('/dev/ttyACM0', 9600)
time.sleep(2)

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

try:
    while True:
        if arduino.in_waiting > 0:
            try:
                data = arduino.readline().decode('utf-8').strip()
                values = data.split(",")
                soil_value = float(values[0].strip())  
                water_value = float(values[1].strip())  
                timestamp = datetime.now()
                temp = round(getTemp(sensor),2)
                humi = round(getHumi(sensor),2)
                query = "INSERT INTO sensor_log (soil, water, temp, humi, timestamp) VALUES (%s, %s, %s, %s, %s)"
                cursor.execute(query, (soil_value, water_value, temp, humi, timestamp))
                db.commit()

                print("Data inserted into DB.")
            except Exception as e:
                print(f"Error parsing data: {e}")
        time.sleep(1)

finally:
    cursor.close()
    db.close()
    print("Database connection closed.")

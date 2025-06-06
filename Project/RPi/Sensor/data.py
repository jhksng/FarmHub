import serial
import mysql.connector
import time
from datetime import datetime

arduino = serial.Serial('/dev/ttyACM0', 9600)
time.sleep(2)

db = mysql.connector.connect(
    host="localhost", 
    user="root", 
    password="root", 
    database="sensor"
)

cursor = db.cursor()

try:
    while True:
        if arduino.in_waiting > 0:
            try:
                data = arduino.readline().decode('utf-8').strip()
                values = data.split(",")
                soil_value = float(values[0].strip())  
                water_value = float(values[1].strip())  
                timestamp = datetime.now()
                temp = 10  
                humi = 20  
                query = "INSERT INTO sensor_data (soil1, water, temp, humi, timestamp) VALUES (%s, %s, %s, %s, %s)"
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

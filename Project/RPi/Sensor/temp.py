import board
import busio
import adafruit_sht31d

i2c = board.I2C()
sensor = adafruit_sht31d.SHT31D(i2c ,address=0x44)
print("sensor obj", sensor)
print("temp:", sensor.temperature)
print("humi:", sensor.relative_humidity)

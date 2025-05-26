
import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setup(16, GPIO.OUT)
GPIO.setup(21, GPIO.OUT)
GPIO.setup(20, GPIO.OUT)
GPIO.setup(26, GPIO.OUT)

while True:
	a,b,c,d = input('input : ').split()
	if int(a)==3 and int(b)==3 and int(c)==3 and int(d) == 3:
		GPIO.cleanup()
		break
	GPIO.output(16, int(d))
	GPIO.output(21, int(a))
	GPIO.output(20, int(b))
	GPIO.output(26, int(c))
	time.sleep(5)

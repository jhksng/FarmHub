import pyfirmata

board = pyfirmata.Arduino('/dev/ttyACM0')
pin9 = board.get_pin('d:9:p')

while True:
	value = int(input("enter value : "))
	pin9.write(value/100.0)

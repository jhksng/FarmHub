from flask import flask, render_template, request
import RPi.GPIO as GPIO
import time

app = Flask(__name__)


#5v
GPIO.setmode(GPIO.BCM)
GPIO.setup(5, GPIO.OUT)
GPIO.setup(6, GPIO.OUT)
GPIO.setup(13, GPIO.OUT)
GPIO.setup(19, GPIO.OUT)
#12v ptc
GPIO.setup(26, GPIO.OUT)

state = {
	5: 1,
	6: 1,
	13: 1,
	19: 1,
	26: 1
}

@app.route('/control')
def control_page():
	return render_template('control.html', state=state)

@app.route('/controller', methods=["POST"])
def controller():
	global state

	if 'LED' in request.form:
		led = int(request.form['LED'])
		GPIO.output(5, led)
		state[5] = led
	if 'CoolerA' in request.form:
		A = int(request.form['CoolerA'])
		GPIO.output(5, A)
		state[5] = A
	if 'CoolerB' in request.form:
		B = int(request.form['CoolerB'])
		GPIO.output(5, B)
		state[5] = B
	if 'WaterPump' in request.form:
		w = int(request.form['WaterPump'])
		GPIO.output(5, w)
		state[5] = w
	if 'PTC' in request.form:
		p = int(request.form['PTC'])
		GPIO.output(5, p)
		state[5] = p
	return render_template('view_control.html', state = state)

if __name__=="__main__":
	app.run(host='0.0.0.0', port=9000, debug=True)

from flask import Flask, render_template, request
import RPi.GPIO as GPIO

# Flask 애플리케이션 생성
app = Flask(__name__)

# GPIO 설정
GPIO.setmode(GPIO.BCM)
GPIO.setup(16, GPIO.OUT)
GPIO.setup(21, GPIO.OUT)
GPIO.setup(20, GPIO.OUT)
GPIO.setup(26, GPIO.OUT)

# 상태 추적을 위한 변수 (초기값 설정)
state = {
    16: 0,
    21: 0,
    20: 0,
    26: 0
}

@app.route('/')
def index():
    # 초기 상태를 포함한 페이지 렌더링
    return render_template('154.html', state=state)

@app.route('/control', methods=['POST'])
def control():
    global state
    # 사용자가 보낸 데이터로 각 핀의 상태 업데이트
    a = int(request.form['a'])
    b = int(request.form['b'])
    c = int(request.form['c'])
    d = int(request.form['d'])
    
    # GPIO 핀 상태 변경
    GPIO.output(16, d)
    GPIO.output(21, a)
    GPIO.output(20, b)
    GPIO.output(26, c)

    # 상태 추적 변수 업데이트
    state = {16: d, 21: a, 20: b, 26: c}
    
    # 상태 변경 후 페이지 렌더링
    return render_template('154.html', state=state)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)

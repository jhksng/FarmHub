import time
import threading
from datetime import datetime, timedelta
from flask import Flask, request
import mysql.connector
import os

# 라우트 파일에서 Blueprint 객체들을 가져옵니다.
from routes.main_routes import main_bp
from routes.control_routes import control_bp
# from routes.camera_routes import camera_bp  # 나중에 추가
# from routes.ai_routes import ai_bp        # 나중에 추가

# GPIO 및 기존 자동 제어 함수들은 여기에 그대로 둡니다.
# ... (이전 답변의 GPIO, DB, 장치 제어, 자동 제어 루프 함수 코드 전체) ...

# Flask 앱 생성
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret_key_1234")

# --- 상태 변수 및 핵심 함수를 앱 컨텍스트에 등록 ---
# 다른 파일(Blueprint)에서 current_app으로 이 변수/함수들에 접근 가능
app.pins = pins
app.device_state = device_state
app.manual_override = manual_override
app.current_loop_thread = current_loop_thread
app.current_crop_name = current_crop_name
app.stop_event = stop_event
app.start_control_loop = start_control_loop
app.get_db_connection = get_db_connection

# --- API 엔드포인트 (JavaScript fetch 요청 처리) ---
# 이 라우트들은 상태를 직접 수정하므로 app.py에 두는 것이 편리합니다.
@app.route('/controller', methods=["POST"])
def controller():
    # ... (이전 답변의 controller 함수 로직 그대로) ...

@app.route('/auto_mode/<string:device_name>', methods=['POST'])
def set_auto_mode(device_name):
    # ... (이전 답변의 set_auto_mode 함수 로직 그대로) ...

# --- Blueprint 등록 ---
app.register_blueprint(main_bp)
app.register_blueprint(control_bp)
# app.register_blueprint(camera_bp) # 나중에 추가
# app.register_blueprint(ai_bp)       # 나중에 추가

if __name__ == "__main__":
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    finally:
        if GPIO_AVAILABLE:
            print("애플리케이션 종료 시 GPIO.cleanup() 실행")
            GPIO.cleanup()

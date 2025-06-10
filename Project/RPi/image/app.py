import os
import glob
from datetime import datetime
import threading
import time

import google.generativeai as genai
import PIL.Image
import mysql.connector
from flask import Flask, request, render_template, send_from_directory, url_for, redirect

# --- 기본 설정 ---
app = Flask(__name__)

# ▼▼▼▼▼ 여기에 실제 Gemini API 키를 입력하세요 ▼▼▼▼▼
GEMINI_API_KEY = 'YOUR_GEMINI_API_KEY'
if GEMINI_API_KEY != 'YOUR_GEMINI_API_KEY':
    genai.configure(api_key=GEMINI_API_KEY)

# GPIO 라이브러리 (가상 모드 포함)
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    print("RPi.GPIO 라이브러리를 찾을 수 없습니다. GPIO 제어는 비활성화됩니다.")
    GPIO_AVAILABLE = False
    class DummyGPIO:
        def setmode(self, mode): pass
        def setup(self, pin, mode, initial=None): pass
        def output(self, pin, value): print(f"DUMMY GPIO: Pin {pin} -> {value}")
        def cleanup(self): pass
        BCM = 11; OUT = 0; LOW = 0; HIGH = 1
    GPIO = DummyGPIO()

# --- 상태 관리 변수 (기존 스마트팜 로직) ---
current_crop_name = "N/A" # 현재 제어중인 작물 이름 (필요시 DB 연동)


# --- 웹 페이지 라우트 ---

@app.route('/')
def index():
    # 메인 페이지는 갤러리 페이지로 바로 연결합니다.
    return redirect(url_for('gallery'))

@app.route('/gallery')
def gallery():
    # photos 디렉토리가 없으면 생성
    if not os.path.exists('photos'):
        os.makedirs('photos')
        
    # photos 디렉토리에서 이미지 파일 목록을 가져옴 (jpg, png, jpeg)
    image_files_path = glob.glob('photos/*.jpg') + glob.glob('photos/*.png') + glob.glob('photos/*.jpeg')
    
    # 전체 경로에서 파일 이름만 추출하고, 최신 파일이 위로 오도록 정렬
    image_filenames = sorted([os.path.basename(p) for p in image_files_path], reverse=True)
    
    return render_template('gallery.html', image_files=image_filenames, current_crop=current_crop_name)

@app.route('/photos/<filename>')
def serve_photo(filename):
    # photos 디렉토리의 파일에 웹 브라우저가 접근할 수 있도록 해주는 경로
    return send_from_directory('photos', filename)

@app.route('/analyze/<filename>', methods=['POST'])
def analyze_photo(filename):
    image_path = os.path.join('photos', filename)

    if GEMINI_API_KEY == 'YOUR_GEMINI_API_KEY':
        return "오류: Gemini API 키가 설정되지 않았습니다."
    if not os.path.exists(image_path):
        return "오류: 분석할 이미지를 찾을 수 없습니다."

    try:
        img = PIL.Image.open(image_path)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')

        # ▼▼▼▼▼▼▼▼▼▼▼ 요청하신 대로 수정한 최종 프롬프트 ▼▼▼▼▼▼▼▼▼▼▼
        prompt_text = """
        이 사진을 보고 아래 형식에 맞춰 딱 두 가지만 한국어로 답변해.
        다른 모든 설명과 문장은 절대 추가하지 마.

        작물 이름: [작물의 이름]
        수확 시기: [예상되는 수확 시기 또는 상태. 예: "즉시 수확 가능", "약 3일 후", "아직 덜 익음"]
        """
        # ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲

        response = model.generate_content([prompt_text, img])
        
        return render_template('gemini_result.html', result_text=response.text, image_file=filename)

    except Exception as e:
        print(f"이미지 분석 중 오류: {e}")
        return f"이미지 분석 중 오류가 발생했습니다: {e}"


# --- 앱 실행 ---
if __name__ == "__main__":
    try:
        # photos 디렉토리가 없으면 시작할 때 생성
        if not os.path.exists('photos'):
            os.makedirs('photos')
        app.run(host='0.0.0.0', port=5000, debug=False)
    finally:
        if GPIO_AVAILABLE:
            print("애플리케이션 종료 시 GPIO.cleanup() 실행")
            GPIO.cleanup()

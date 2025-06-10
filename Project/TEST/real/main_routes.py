from flask import Blueprint, render_template

# 'main'이라는 이름의 Blueprint 객체 생성
main_bp = Blueprint('main', __name__)

# '/' 주소로 접속하면 index() 함수가 실행됨
@main_bp.route('/')
def index():
    # templates 폴더의 index.html 파일을 렌더링하여 사용자에게 보여줌
    return render_template('index.html')

# /status 주소를 위한 임시 라우트
@main_bp.route('/status')
def status():
    return render_template('status.html') # 나중에 status.html 파일 생성 필요

# /camera 주소를 위한 임시 라우트
@main_bp.route('/camera')
def camera_page():
    return render_template('camera.html')

# /ai 주소를 위한 임시 라우트
@main_bp.route('/ai')
def ai_page():
    return render_template('ai.html')

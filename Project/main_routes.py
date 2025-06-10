from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/status')
def status():
    # 여기에 작물 상태를 DB에서 읽어오는 로직 추가
    return render_template('status.html') # status.html 생성 필요

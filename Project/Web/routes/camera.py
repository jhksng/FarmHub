from flask import Blueprint, render_template, session, redirect, url_for
import os
from datetime import datetime
from utils.camera_utils import capture_photo
from utils.db import get_db

camera_bp = Blueprint('camera', __name__)

@camera_bp.route('/camera')
def camera():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT selected_crop FROM users WHERE id = %s", (user_id,))
    result = cursor.fetchone()
    
    if not result or not result['selected_crop']:
        return "선택된 작물이 없습니다.", 403
    
    selected_crop = result['selected_crop']

    # 사진 촬영
    filename = capture_photo(selected_crop)

    # 최신 파일 찾기
    folder = 'static/photos'
    files = [f for f in os.listdir(folder) if f.endswith('.jpg') and selected_crop in f]
    files.sort(reverse=True)
    latest_photo = files[0] if files else None

    return render_template('camera.html', photo_filename=latest_photo)
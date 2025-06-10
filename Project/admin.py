from flask import Blueprint, render_template, request, redirect, flash, session, url_for
from utils.db import get_db
from functools import wraps
import os
from werkzeug.utils import secure_filename

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# 관리자 권한 확인 데코레이터
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('username') != 'admin':
            flash("관리자만 접근 가능합니다.")
            return redirect('/')
        return f(*args, **kwargs)
    return decorated_function

# 관리자 대시보드
@admin_bp.route('/')
@admin_required
def dashboard():
    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT 
            ci.crop AS crop_name,
            sl.timestamp,
            sl.temp,
            sl.humi,
            sl.soil,
            sl.water,
            sl.light,
            sl.growth
        FROM sensor_log sl
        JOIN crop_info ci ON sl.crop_id = ci.id
        ORDER BY sl.id DESC
        LIMIT 50
    """)
    records = cur.fetchall()

    for row in records:
        row['datetime'] = row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')

    cur.execute("SELECT * FROM users ORDER BY id ASC")
    users = cur.fetchall()

    cur.execute("""
        SELECT id, crop, target_temp, target_humi, target_soil,
               target_light, target_growth
        FROM crop_info ORDER BY crop ASC
    """)
    crops = cur.fetchall()

    cur.close()
    db.close()

    content = render_template('admin_dashboard_content.html', records=records, users=users, crops=crops)
    return render_template('admin.html', content=content)

# 수동 제어 페이지
@admin_bp.route('/control', methods=['GET', 'POST'])
@admin_required
def control():
    if request.method == 'POST':
        device = request.form.get('device')
        flash(f"{device} 제어 명령 전송됨")
    return render_template('admin.html', content=render_template('admin_control.html'))

# 작물 추가 페이지
@admin_bp.route('/add_crop', methods=['GET', 'POST'])
@admin_required
def add_crop():
    if request.method == 'POST':
        crop = request.form['crop']
        temp = request.form['temp']
        humi = request.form['humi']
        soil = request.form['soil']
        light = request.form['light']
        growth = request.form['growth']
        description = request.form['description']
        image = request.files['image']

        filename = None
        if image and image.filename != '':
            filename = secure_filename(image.filename)
            image.save(os.path.join('static/images/crop_images', filename))

        db = get_db()
        cur = db.cursor()
        cur.execute("""
            INSERT INTO crop_info (
                crop, target_temp, target_humi, target_soil,
                target_light, target_growth,
                description, image
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (crop, temp, humi, soil, light, growth, description, filename))
        db.commit()
        cur.close()
        db.close()

        flash("작물이 성공적으로 추가되었습니다.")
        return redirect(url_for('admin.dashboard'))

    return render_template('admin.html', content=render_template('admin_add_crop.html'))

# 사용자 삭제
@admin_bp.route('/delete_user/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    db.commit()
    cur.close()
    db.close()
    flash("사용자가 삭제되었습니다.")
    return redirect(url_for('admin.dashboard'))

# 작물 수정
@admin_bp.route('/edit_crop/<int:crop_id>', methods=['GET', 'POST'])
@admin_required
def edit_crop(crop_id):
    db = get_db()
    cur = db.cursor(dictionary=True)

    if request.method == 'POST':
        crop = request.form['crop']
        temp = request.form['temp']
        humi = request.form['humi']
        soil = request.form['soil']
        light = request.form['light']
        growth = request.form['growth']
        description = request.form['description']

        cur = db.cursor()
        cur.execute("""
            UPDATE crop_info
            SET crop = %s,
                target_temp = %s,
                target_humi = %s,
                target_soil = %s,
                target_light = %s,
                target_growth = %s,
                description = %s
            WHERE id = %s
        """, (crop, temp, humi, soil, light, growth, description, crop_id))
        db.commit()
        cur.close()
        db.close()

        flash("작물 정보가 수정되었습니다.")
        return redirect(url_for('admin.dashboard'))

    cur.execute("SELECT * FROM crop_info WHERE id = %s", (crop_id,))
    crop = cur.fetchone()
    cur.close()
    db.close()

    if not crop:
        flash("작물을 찾을 수 없습니다.")
        return redirect(url_for('admin.dashboard'))

    return render_template('admin.html', content=render_template('admin_edit_crop.html', crop=crop))

# 작물 삭제
@admin_bp.route('/delete_crop/<int:crop_id>', methods=['POST'])
@admin_required
def delete_crop(crop_id):
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM crop_info WHERE id = %s", (crop_id,))
    db.commit()
    cur.close()
    db.close()
    flash("작물이 삭제되었습니다.")
    return redirect(url_for('admin.dashboard'))

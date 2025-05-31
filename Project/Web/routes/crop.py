from flask import Blueprint, render_template, request, redirect, flash, session
from utils.db import get_db

crop_bp = Blueprint('crop', __name__)

# 유틸 함수
def get_selected_crop(user_id):
    cur = get_db().connection.cursor()
    cur.execute("SELECT selected_crop FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    return row['selected_crop'] if row else None

@crop_bp.route('/cropSelect', methods=['GET', 'POST'])
def crop_select():
    user_id = session.get('user_id')
    cur = get_db().connection.cursor()

    cur.execute("SELECT * FROM crop_info")
    crops = cur.fetchall()

    if request.method == 'POST':
        selected_crop = request.form.get('crop_name')
    else:
        selected_crop = request.values.get('crop_name') or get_selected_crop(user_id) or '상추'

    cur.execute("SELECT * FROM crop_info WHERE crop = %s", (selected_crop,))
    selected_info = cur.fetchone()
    cur.close()

    return render_template('cropSelect.html', crops=crops, selected_info=selected_info, selected_crop=selected_crop)

@crop_bp.route('/select_crop', methods=['POST'])
def select_crop():
    user_id = session.get('user_id')
    crop_name = request.form.get('crop_name')

    if not crop_name:
        flash("작물 선택 오류입니다.")
        return redirect('/cropSelect')

    cur = get_db().connection.cursor()
    cur.execute("UPDATE users SET selected_crop = %s WHERE id = %s", (crop_name, user_id))
    get_db().connection.commit()
    cur.close()

    return redirect('/cropInformation')

@crop_bp.route('/custom_crop', methods=['POST'])
def custom_crop():
    user_id = session.get('user_id')
    crop_name = request.form['crop']
    temp = request.form['temp']
    humidity = request.form['humidity']
    light = request.form['light']
    water = request.form['water']
    growth = request.form['growth']

    cur = get_db().connection.cursor()
    cur.execute("SELECT id FROM crop_info WHERE crop = %s", (crop_name,))
    existing = cur.fetchone()

    if existing:
        cur.execute("""
            UPDATE crop_info
            SET temp=%s, humidity=%s, light=%s, water=%s, growth=%s
            WHERE crop=%s
        """, (temp, humidity, light, water, growth, crop_name))
    else:
        cur.execute("""
            INSERT INTO crop_info (crop, temp, humidity, light, water, growth)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (crop_name, temp, humidity, light, water, growth))

    cur.execute("UPDATE users SET selected_crop = %s WHERE id = %s", (crop_name, user_id))
    get_db().connection.commit()
    cur.close()

    return redirect('/cropInformation')

@crop_bp.route('/confirm_crop')
def confirm_crop():
    crop_name = request.args.get('crop')
    user_id = session.get('user_id')

    cur = get_db().connection.cursor()
    if crop_name == '사용자 지정':
        cur.execute("SELECT * FROM custom_crop_info WHERE user_id = %s", (user_id,))
        crop = cur.fetchone()
    else:
        cur.execute("SELECT * FROM crop_info WHERE crop = %s", (crop_name,))
        crop = cur.fetchone()
    cur.close()

    if not crop:
        flash("해당 작물 정보를 찾을 수 없습니다.")
        return redirect('/cropSelect')

    return render_template('confirm_crop.html', crop=crop)

@crop_bp.route('/cropInformation')
def crop_information():
    user_id = session.get('user_id')
    cur = get_db().connection.cursor()

    cur.execute("SELECT selected_crop FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    selected_crop = row['selected_crop'] if row else '상추'

    cur.execute("SELECT * FROM crop_info WHERE crop = %s", (selected_crop,))
    crop_info = cur.fetchone()

    cur.execute("SELECT * FROM crop_logs ORDER BY id DESC LIMIT 1")
    latest_log = cur.fetchone()
    cur.close()

    return render_template('cropInformation.html', record=latest_log, info=crop_info)

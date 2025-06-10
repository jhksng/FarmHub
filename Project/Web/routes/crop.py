from flask import Blueprint, render_template, request, redirect, flash, session
from utils.db import get_db

crop_bp = Blueprint('crop', __name__)

# 유틸 함수: 사용자 선택 작물 조회
def get_selected_crop(user_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT selected_crop FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    return row['selected_crop'] if row else None


# 작물 선택 화면
@crop_bp.route('/cropSelect', methods=['GET', 'POST'])
def crop_select():
    user_id = session.get('user_id')
    if not user_id:
        flash("로그인이 필요합니다.")
        return redirect('/login')

    db = get_db()
    cur = db.cursor(dictionary=True)

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


# 작물 선택 반영
@crop_bp.route('/select_crop', methods=['POST'])
def select_crop():
    user_id = session.get('user_id')
    if not user_id:
        flash("로그인이 필요합니다.")
        return redirect('/login')

    crop_name = request.form.get('crop_name')
    if not crop_name:
        flash("작물 선택 오류입니다.")
        return redirect('/cropSelect')

    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE users SET selected_crop = %s, selected_time = NOW() WHERE id = %s", (crop_name, user_id))
    db.commit()
    cur.close()

    return redirect('/cropInformation')


# 사용자 정의 작물 등록/수정
@crop_bp.route('/custom_crop', methods=['POST'])
def custom_crop():
    user_id = session.get('user_id')
    if not user_id:
        flash("로그인이 필요합니다.")
        return redirect('/login')

    crop_name = request.form['crop']
    temp = request.form['temp']
    humi = request.form['humi']
    soil = request.form['soil']
    light = request.form['light']
    growth = request.form['growth']

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM crop_info WHERE crop = %s", (crop_name,))
    existing = cur.fetchone()

    if existing:
        cur.execute("""
            UPDATE crop_info
            SET target_temp=%s, target_humi=%s, target_soil=%s,
                target_light=%s, target_growth=%s
            WHERE crop=%s
        """, (temp, humi, soil, light, growth, crop_name))
    else:
        cur.execute("""
            INSERT INTO crop_info (crop, target_temp, target_humi, target_soil,
                                   target_light, target_growth)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (crop_name, temp, humi, soil, light, growth))

    cur.execute("UPDATE users SET selected_crop = %s, selected_time = NOW() WHERE id = %s", (crop_name, user_id))
    db.commit()
    cur.close()

    return redirect('/cropInformation')


# 작물 정보 확인 화면
@crop_bp.route('/confirm_crop')
def confirm_crop():
    crop_name = request.args.get('crop')
    if not crop_name:
        flash("작물 이름이 없습니다.")
        return redirect('/cropSelect')

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM crop_info WHERE crop = %s", (crop_name,))
    crop = cur.fetchone()
    cur.close()

    if not crop:
        flash("해당 작물 정보를 찾을 수 없습니다.")
        return redirect('/cropSelect')

    return render_template('confirm_crop.html', crop=crop)


# 선택 작물 정보 및 센서 로그 확인 화면
@crop_bp.route('/cropInformation')
def crop_information():
    user_id = session.get('user_id')
    if not user_id:
        flash("로그인이 필요합니다.")
        return redirect('/login')

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("SELECT selected_crop FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    selected_crop = row['selected_crop'] if row else '상추'

    # 작물 정보 가져오기
    cur.execute("SELECT * FROM crop_info WHERE crop = %s", (selected_crop,))
    crop_info = cur.fetchone()

    # 선택한 작물 기준으로 최신 센서 로그 가져오기
    cur.execute("""
        SELECT * FROM sensor_log
        WHERE crop_id = (SELECT id FROM crop_info WHERE crop = %s)
        ORDER BY id DESC LIMIT 1
    """, (selected_crop,))
    latest_log = cur.fetchone()

    cur.close()

    return render_template('cropInformation.html', record=latest_log, info=crop_info)

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from datetime import datetime
import threading

control_bp = Blueprint('control', __name__)

@control_bp.route('/select_crop')
def select_crop():
    return render_template('select_crop.html')

@control_bp.route('/start_system', methods=['POST'])
def start_system():
    crop_name = request.form['crop'].strip()
    
    # 메인 앱(app.py)의 함수와 변수 사용
    db = current_app.get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT crop FROM crop_info WHERE crop = %s", (crop_name,))
    if not cursor.fetchone():
        flash("오류: DB에 없는 작물입니다.", 'error')
        return redirect(url_for('control.select_crop'))

    if current_app.current_loop_thread and current_app.current_loop_thread.is_alive():
        current_app.stop_event.set()
        current_app.current_loop_thread.join(timeout=5)

    now_time = datetime.now()
    cursor.execute("UPDATE users SET selected_crop=%s, selected_time=%s LIMIT 1", (crop_name, now_time))
    cursor.execute("UPDATE control_state SET light_on_seconds_acc=0, light_last_update_time=%s LIMIT 1", (now_time,))
    db.commit()
    
    current_app.stop_event = threading.Event()
    current_app.current_crop_name = crop_name
    
    new_thread = threading.Thread(
        target=current_app.start_control_loop, 
        args=(crop_name, current_app.stop_event), 
        daemon=True
    )
    new_thread.start()
    current_app.current_loop_thread = new_thread
    
    flash(f"'{crop_name}' 자동 제어를 시작합니다.", 'success')
    return redirect(url_for('control.manual_control'))

@control_bp.route('/control')
def manual_control():
    # control.html 템플릿에 필요한 변수 전달
    template_vars = {
        "device_state": current_app.device_state,
        "manual_override": current_app.manual_override,
        "pins": current_app.pins
    }
    return render_template('control.html', **template_vars)

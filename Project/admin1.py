# MODIFIED: 필요한 모듈들을 모두 import 합니다.
from flask import (Blueprint, render_template, request, redirect, flash, 
                   session, url_for, current_app)
from functools import wraps
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import threading

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# ... (admin_required 데코레이터는 그대로 둡니다) ...
def admin_required(f):
    # ...
    
# 관리자 대시보드
@admin_bp.route('/')
@admin_required
def dashboard():
    # MODIFIED: DB 연결 방식을 app.py를 통해 가져오도록 통일합니다.
    # 이렇게 하면 DB 설정이 바뀌어도 app.py만 수정하면 됩니다.
    db = current_app.get_db_connection()
    cur = db.cursor(dictionary=True)
    # ... (나머지 대시보드 로직은 그대로) ...
    cur.close()
    db.close()
    content = render_template('admin_dashboard_content.html', records=records, users=users, crops=crops)
    return render_template('admin.html', content=content)


# REPLACED: 기존의 비어있던 control() 함수를 아래 내용으로 완전히 교체합니다.
@admin_bp.route('/control')
@admin_required
def control():
    """
    메인 앱(app.py)의 현재 장치 상태를 가져와
    수동 제어 UI(admin_control.html)에 전달하고,
    이것을 다시 메인 레이아웃(admin.html)에 채워서 보여줍니다.
    """
    template_vars = {
        "device_state": current_app.device_state,
        "manual_override": current_app.manual_override,
        "pins": current_app.pins
    }
    content_html = render_template('admin_control.html', **template_vars)
    return render_template('admin.html', content=content_html)


# NEW: 파일의 적당한 위치에 새로운 라우트 함수를 추가합니다.
@admin_bp.route('/start', methods=['GET', 'POST'])
@admin_required
def start_control_system():
    if request.method == 'POST':
        crop_name = request.form['crop'].strip()
        
        db = current_app.get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT crop FROM crop_info WHERE crop = %s", (crop_name,))
        if not cursor.fetchone():
            flash("오류: DB에 없는 작물입니다.")
            return redirect(url_for('admin.start_control_system'))

        if current_app.current_loop_thread and current_app.current_loop_thread.is_alive():
            current_app.stop_event.set()
            current_app.current_loop_thread.join(timeout=5)

        now_time = datetime.now()
        cursor.execute("UPDATE users SET selected_crop=%s, selected_time=%s LIMIT 1", (crop_name, now_time))
        cursor.execute("UPDATE control_state SET light_on_seconds_acc=0, light_last_update_time=%s LIMIT 1", (now_time,))
        db.commit()
        cursor.close()
        db.close()
        
        current_app.stop_event = threading.Event()
        current_app.current_crop_name = crop_name
        
        new_thread = threading.Thread(
            target=current_app.start_control_loop, 
            args=(crop_name, current_app.stop_event), 
            daemon=True
        )
        new_thread.start()
        # 주의: 스레드 객체는 current_app을 통해 직접 수정이 어려울 수 있으므로
        # 실제로는 app.py에 스레드를 관리하는 함수를 두고 호출하는 것이 더 안정적입니다.
        # 이 코드에서는 단순성을 위해 전역 변수를 직접 참조하는 것으로 가정합니다.
        # current_app.current_loop_thread = new_thread (이 부분은 주의가 필요)
        
        flash(f"'{crop_name}' 작물에 대한 자동 제어를 시작합니다.")
        return redirect(url_for('admin.control'))

    # GET 요청일 때
    content_html = render_template('admin_start_control.html')
    return render_template('admin.html', content=content_html)


# ... (add_crop, delete_user, edit_crop, delete_crop 등 나머지 함수는 그대로 둡니다) ...
# 단, DB 연결 부분(db = get_db())을 db = current_app.get_db_connection() 으로 바꿔주면 더 좋습니다.

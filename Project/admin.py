# /routes/admin.py
# 파일 상단에 필요한 모듈들을 추가합니다.
from flask import Blueprint, render_template, request, flash, session, url_for, redirect, current_app
from datetime import datetime
import threading

# get_db_connection 함수를 메인 app.py에서 가져오도록 수정해야 할 수 있습니다.
# 이 부분은 프로젝트 전체 구조에 따라 달라집니다.
# 만약 app.py에 get_db_connection이 있다면, 여기서는 그 함수를 직접 호출해야 합니다.
# 지금은 임시로 있다고 가정합니다.
from ..app import get_db_connection 

# ... 기존 admin_bp 및 다른 라우트들 ...

# ✨새로운 제어 시작/변경 페이지 라우트
@admin_bp.route('/start', methods=['GET', 'POST'])
@admin_required
def start_control_system():
    # POST 요청일 때 (사용자가 폼을 제출했을 때)
    if request.method == 'POST':
        crop_name = request.form['crop'].strip()
        
        # app.py에 있던 자동 제어 시작 로직을 그대로 가져옵니다.
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT crop FROM crop_info WHERE crop = %s", (crop_name,))
        if not cursor.fetchone():
            flash("오류: 유효한 작물이 아닙니다.")
            return redirect(url_for('admin.start_control_system'))

        # 메인 앱의 전역 스레드 변수에 접근 (current_app 사용)
        if current_app.current_loop_thread and current_app.current_loop_thread.is_alive():
            current_app.stop_event.set()
            current_app.current_loop_thread.join(timeout=5)

        now_time = datetime.now()
        cursor.execute("UPDATE users SET selected_crop=%s, selected_time=%s LIMIT 1", (crop_name, now_time))
        cursor.execute("UPDATE control_state SET light_on_seconds_acc=0, light_last_update_time=%s LIMIT 1", (now_time,))
        db.commit()
        cursor.close()
        db.close()
        
        # 메인 앱의 자동 제어 함수와 전역 변수를 사용하여 새 스레드 시작
        current_app.stop_event = threading.Event()
        current_app.current_crop_name = crop_name
        # start_control_loop 함수 자체도 current_app을 통해 접근해야 할 수 있습니다.
        # 가장 좋은 방법은 start_control_loop 함수를 app.py에 두고,
        # 이 라우트에서 스레드를 직접 생성하는 대신, 앱의 다른 함수를 호출하는 것입니다.
        # 여기서는 단순화를 위해 직접 생성하는 것으로 가정합니다.
        from ..app import start_control_loop # 메인 앱의 함수를 import
        
        new_thread = threading.Thread(target=start_control_loop, args=(crop_name, current_app.stop_event), daemon=True)
        new_thread.start()
        current_app.current_loop_thread = new_thread
        
        flash(f"{crop_name} 자동 제어를 시작합니다.")
        return redirect(url_for('admin.control')) # 시작 후 수동 제어 페이지로 이동

    # GET 요청일 때 (페이지를 처음 열었을 때)
    content_html = render_template('admin_start_control.html')
    return render_template('admin.html', content=content_html)

from flask import Flask, render_template, request, redirect, flash, session
from flask_mysqldb import MySQL
from datetime import timedelta
from functools import wraps
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# MySQL 설정
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_PORT'] = 3306
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'port#4514'
app.config['MYSQL_DB'] = 'smartparm'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

# 최신 로그 불러오기
def get_latest_records(table_name, limit=50):
    cur = mysql.connection.cursor()
    cur.execute(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT %s", (limit,))
    records = cur.fetchall()
    cur.close()
    return records

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cur.fetchone()
        cur.close()

        if user:
            session['username'] = username
            session['user_id'] = user['id']
            flash('로그인 성공')
            return redirect('/')
        else:
            flash('아이디 또는 비밀번호가 틀렸습니다.')
            return redirect('/signin')

    return render_template('signin.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            flash('이미 존재하는 사용자입니다.')
            return redirect('/signup')

        cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
        mysql.connection.commit()
        cur.close()

        flash('회원가입이 완료되었습니다!')
        return redirect('/signin')

    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('로그아웃되었습니다.')
    return redirect('/')

@app.route('/cropSelect', methods=['GET', 'POST'])
def cropSelect():
    user_id = session.get('user_id')
    cur = mysql.connection.cursor()

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


@app.route('/select_crop', methods=['POST'])
def select_crop():
    user_id = session.get('user_id')
    crop_name = request.form.get('crop_name')

    if not crop_name:
        flash("작물 선택 오류입니다.")
        return redirect('/cropSelect')

    cur = mysql.connection.cursor()
    cur.execute("UPDATE users SET selected_crop = %s WHERE id = %s", (crop_name, user_id))
    mysql.connection.commit()
    cur.close()

    return redirect('/cropInformation')

@app.route('/custom_crop', methods=['POST'])
def custom_crop():
    user_id = session.get('user_id')

    crop_name = request.form['crop']
    temp = request.form['temp']
    humidity = request.form['humidity']
    light = request.form['light']
    water = request.form['water']
    growth = request.form['growth']

    cur = mysql.connection.cursor()

    # 이미 같은 이름의 사용자 지정 작물이 있으면 갱신, 없으면 삽입
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

    # 사용자 선택 작물 설정
    cur.execute("UPDATE users SET selected_crop = %s WHERE id = %s", (crop_name, user_id))
    mysql.connection.commit()
    cur.close()

    return redirect('/cropInformation')


@app.route('/confirm_crop')
def confirm_crop():
    crop_name = request.args.get('crop')
    user_id = session.get('user_id')

    cur = mysql.connection.cursor()
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

@app.route('/cropInformation')
def cropInfo():
    user_id = session.get('user_id')
    cur = mysql.connection.cursor()

    cur.execute("SELECT selected_crop FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    selected_crop = row['selected_crop'] if row else '상추' 

    cur.execute("SELECT * FROM crop_info WHERE crop = %s", (selected_crop,))
    crop_info = cur.fetchone()

    cur.execute("SELECT * FROM crop_logs ORDER BY id DESC LIMIT 1")
    latest_log = cur.fetchone()
    cur.close()

    return render_template('cropInformation.html', record=latest_log, info=crop_info)

@app.route('/camera')
def camera():
    return render_template('camera.html')

# @app.route('/datarecord')
# def data_record():
#     if 'username' not in session:
#         flash("로그인이 필요합니다.")
#         return redirect('/signin')
#     if session.get('username') != 'admin':
#         flash("접근 권한이 없습니다. 관리자만 접근할 수 있습니다.")
#         return redirect('/signin')

#     cur = mysql.connection.cursor()
#     query = """
#         SELECT 
#             ci.crop AS crop_name,
#             cl.timestamp,
#             cl.temp,
#             cl.humidity,
#             cl.light_seconds,
#             cl.growth
#         FROM crop_logs cl
#         JOIN crop_info ci ON cl.crop_id = ci.id
#         ORDER BY cl.id DESC
#         LIMIT 50
#     """
#     cur.execute(query)
#     result = cur.fetchall()
#     cur.close()

#     for row in result:
#         row['datetime'] = row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
#         seconds = row['light_seconds']
#         row['light_str'] = f"{seconds // 3600}:{(seconds % 3600) // 60:02}:{seconds % 60:02}"

#     return render_template('datarecord.html', records=result)

# 유틸 함수: 사용자 선택 작물 조회
def get_selected_crop(user_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT selected_crop FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    return row['selected_crop'] if row else None

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('username') != 'admin':
            flash("관리자만 접근 가능합니다.")
            return redirect('/')
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin')
@admin_required
def admin_dashboard():
    cur = mysql.connection.cursor()

    # 최근 센서 로그
    cur.execute("""
        SELECT 
            ci.crop AS crop_name,
            cl.timestamp,
            cl.temp,
            cl.humidity,
            cl.light_seconds,
            cl.growth
        FROM crop_logs cl
        JOIN crop_info ci ON cl.crop_id = ci.id
        ORDER BY cl.id DESC
        LIMIT 50
    """)
    records = cur.fetchall()

    for row in records:
        row['datetime'] = row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        seconds = row['light_seconds']
        row['light_str'] = f"{seconds // 3600}:{(seconds % 3600) // 60:02}:{seconds % 60:02}"

    # 사용자 목록
    cur.execute("SELECT id, username, selected_crop FROM users ORDER BY id ASC")
    users = cur.fetchall()

    # 작물 목록
    cur.execute("SELECT id, crop, temp, humidity, light, water, growth FROM crop_info ORDER BY crop ASC")
    crops = cur.fetchall()

    cur.close()

    content = render_template('admin_dashboard_content.html', records=records, users=users, crops=crops)
    return render_template('admin.html', content=content)


# 수동 제어 페이지
@app.route('/admin/control', methods=['GET', 'POST'])
@admin_required
def admin_control():
    if request.method == 'POST':
        device = request.form.get('device')
        # 여기에 수동 제어 로직 (GPIO or 시리얼)
        flash(f"{device} 제어 명령 전송됨")
    return render_template('admin.html', content=render_template('admin_control.html'))

# 작물 추가 페이지
@app.route('/admin/add_crop', methods=['GET', 'POST'])
@admin_required
def admin_add_crop():
    if request.method == 'POST':
        crop = request.form['crop']
        temp = request.form['temp']
        humidity = request.form['humidity']
        light = request.form['light']
        water = request.form['water']
        growth = request.form['growth']
        description = request.form['description']
        image = request.files['image']

        filename = None
        if image and image.filename != '':
            filename = secure_filename(image.filename)
            image.save(os.path.join('static/images/crop_images', filename))

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO crop_info (crop, temp, humidity, light, water, growth, description, image)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (crop, temp, humidity, light, water, growth, description, filename))
        mysql.connection.commit()
        cur.close()

        flash("작물이 성공적으로 추가되었습니다.")
        return redirect('/admin')

    return render_template('admin.html', content=render_template('admin_add_crop.html'))

# 사용자 삭제
@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    mysql.connection.commit()
    cur.close()
    flash("사용자가 삭제되었습니다.")
    return redirect('/admin')


# 작물 편집
@app.route('/admin/edit_crop/<int:crop_id>', methods=['GET', 'POST'])
@admin_required
def edit_crop(crop_id):
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        crop = request.form['crop']
        temp = request.form['temp']
        humidity = request.form['humidity']
        light = request.form['light']
        water = request.form['water']
        growth = request.form['growth']
        description = request.form['description']

        cur.execute("""
            UPDATE crop_info
            SET crop = %s, temp = %s, humidity = %s, light = %s,
                water = %s, growth = %s, description = %s
            WHERE id = %s
        """, (crop, temp, humidity, light, water, growth, description, crop_id))
        mysql.connection.commit()
        cur.close()

        flash("작물 정보가 수정되었습니다.")
        return redirect('/admin')

    # GET 요청이면 기존 정보 가져오기
    cur.execute("SELECT * FROM crop_info WHERE id = %s", (crop_id,))
    crop = cur.fetchone()
    cur.close()

    if not crop:
        flash("작물을 찾을 수 없습니다.")
        return redirect('/admin')

    return render_template('admin.html', content=render_template('admin_edit_crop.html', crop=crop))


# 작물 삭제
@app.route('/admin/delete_crop/<int:crop_id>', methods=['POST'])
@admin_required
def delete_crop(crop_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM crop_info WHERE id = %s", (crop_id,))
    mysql.connection.commit()
    cur.close()
    flash("작물이 삭제되었습니다.")
    return redirect('/admin')


if __name__ == '__main__':
    app.debug = True
    app.run()

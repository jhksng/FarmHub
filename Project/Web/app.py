from flask import Flask, render_template, request, redirect, flash, session
from flask_mysqldb import MySQL

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

@app.route('/cropSelect', methods=['GET', 'POST'])
def cropSelect():
    user_id = session.get('user_id')
    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM crop_info")
    crops = cur.fetchall()

    # 선택된 작물 처리
    if request.method == 'POST':
        selected_crop = request.form.get('crop_name')
    else:
        selected_crop = request.values.get('crop_name') or get_selected_crop(user_id) or '상추'

    if selected_crop == '사용자 지정':
        cur.execute("SELECT * FROM custom_crop_info WHERE user_id = %s", (user_id,))
    else:
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
    crop = request.form['crop']
    temp = request.form['temp']
    humidity = request.form['humidity']
    light = request.form['light']
    water = request.form['water']
    growth = request.form['growth']

    cur = mysql.connection.cursor()

    # 기존 사용자 지정 작물 삭제 후 새로 삽입
    cur.execute("DELETE FROM custom_crop_info WHERE user_id = %s", (user_id,))
    cur.execute("""
        INSERT INTO custom_crop_info (user_id, crop, temp, humidity, light, water, growth)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (user_id, crop, temp, humidity, light, water, growth))

    # 선택 작물도 사용자 지정으로 변경
    cur.execute("UPDATE users SET selected_crop = '사용자 지정' WHERE id = %s", (user_id,))
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

    if selected_crop == '사용자 지정':
        cur.execute("SELECT * FROM custom_crop_info WHERE user_id = %s", (user_id,))
    else:
        cur.execute("SELECT * FROM crop_info WHERE crop = %s", (selected_crop,))
    crop_info = cur.fetchone()

    cur.execute("SELECT * FROM crop_logs ORDER BY id DESC LIMIT 1")
    latest_log = cur.fetchone()
    cur.close()

    return render_template('cropInformation.html', record=latest_log, info=crop_info)

@app.route('/camera')
def camera():
    return render_template('camera.html')

@app.route('/datarecord')
def data_record():
    if 'username' not in session:
        flash("로그인이 필요합니다.")
        return redirect('/signin')
    if session.get('username') != 'admin':
        flash("접근 권한이 없습니다. 관리자만 접근할 수 있습니다.")
        return redirect('/signin')

    record = get_latest_records("crop_logs")
    return render_template('datarecord.html', record=record)

# 유틸 함수: 사용자 선택 작물 조회
def get_selected_crop(user_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT selected_crop FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    return row['selected_crop'] if row else None

if __name__ == '__main__':
    app.debug = True
    app.run()

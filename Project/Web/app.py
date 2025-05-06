from flask import Flask, render_template, request, redirect, flash
from flask import session
from flask_mysqldb import MySQL

app= Flask(__name__)
app.secret_key = 'your_secret_key_here'

# DB 연결 함수
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_PORT'] = 3306
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'port#4514'
app.config['MYSQL_DB'] = 'smartparm'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor' 

mysql = MySQL(app)

def get_latest_records(table_name, limit=50):
    cur = mysql.connection.cursor()
    query = f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT {limit}"
    cur.execute(query)
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
        cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
        mysql.connection.commit()
        cur.close()

        flash('로그인 성공')
        return render_template('home.html')

    return render_template('signin.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur = mysql.connection.cursor()

        # 중복 사용자 검사
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        existing_user = cur.fetchone()

        if existing_user:
            flash('이미 존재하는 사용자입니다.')
            return redirect('/signup')
        else:
            cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
            mysql.connection.commit()
            cur.close()

            flash('회원가입이 완료되었습니다!')
            return redirect('/')

    return render_template('signup.html')

@app.route('/cropSelect')
def cropSelect():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM crop_info")
    crops = cur.fetchall()
    cur.close()
    return render_template('cropSelect.html', crops=crops)

@app.route('/confirm_crop')
def confirm_crop():
    crop_name = request.args.get('crop')
    if not crop_name:
        flash("작물을 선택해주세요.")
        return redirect('/cropSelect')

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM crop_info WHERE crop = %s", (crop_name,))
    crop = cur.fetchone()
    cur.close()

    if not crop:
        flash("해당 작물 정보를 찾을 수 없습니다.")
        return redirect('/cropSelect')

    return render_template('confirm_crop.html', crop=crop)

@app.route('/select_crop', methods=['POST'])
def select_crop():
    crop_name = request.form.get('crop_name')
    if not crop_name:
        flash("작물 선택 오류입니다.")
        return redirect('/cropSelect')

    session['selected_crop'] = crop_name
    return redirect('/cropInformation')

@app.route('/cropInformation', methods=['GET', 'POST'])
def cropInfo():
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        selected_crop = request.form['crop_name']
        session['selected_crop'] = selected_crop    # 세션에 저장
    else:
        #세션에 저장된 작물명을 사용
        selected_crop = session.get('selected_crop')
        if not selected_crop:
            cur.execute("SELECT crop FROM crop_info LIMIT 1")
            crop_row = cur.fetchone()
            if not crop_row:
                cur.close()
                flash("작물 정보가 없습니다.")
                return redirect('/cropSelect')
            selected_crop = crop_row['crop']

    cur.execute("SELECT * FROM crop_logs ORDER BY id DESC LIMIT 1")
    latest_log = cur.fetchone()

    cur.execute("SELECT * FROM crop_info WHERE crop = %s", (selected_crop,))
    crop_info = cur.fetchone()
    cur.close()

    return render_template('cropInformation.html', record=latest_log, info=crop_info)

@app.route('/datarecord')

def data_record():
   records = get_latest_records("crop_logs")
   return render_template('datarecord.html', records=records)

if __name__ == '__main__':
    app.debug = True
    app.run()

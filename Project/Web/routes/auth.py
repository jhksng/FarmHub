from flask import Blueprint, request, render_template, redirect, session, flash
from utils.db import get_db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cur = db.cursor(dictionary=True)
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


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            flash('이미 존재하는 사용자입니다.')
            return redirect('/signup')

        cur = db.cursor()  # INSERT에는 dictionary=True 필요 없음
        cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
        db.commit()
        cur.close()

        flash('회원가입이 완료되었습니다!')
        return redirect('/signin')
    return render_template('signup.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('로그아웃되었습니다.')
    return redirect('/')

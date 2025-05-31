from functools import wraps
from flask import session, flash, redirect

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('username') != 'admin':
            flash("관리자만 접근 가능합니다.")
            return redirect('/')
        return f(*args, **kwargs)
    return decorated_function

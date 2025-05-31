from flask import Flask
from flask_mysqldb import MySQL
from config import Config
from routes import register_blueprints
from utils.db import register_mysql

app = Flask(__name__)
app.config.from_object(Config)

# MySQL 초기화 및 등록
mysql = MySQL(app)
register_mysql(mysql)

# 블루프린트 등록
register_blueprints(app)

if __name__ == '__main__':
    app.run(debug=True)

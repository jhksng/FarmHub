from flask import Flask
from config import Config
from routes import register_blueprints
from utils import db

app = Flask(__name__)
app.config.from_object(Config)

app.teardown_appcontext(db.close_db)

# 블루프린트 등록
register_blueprints(app)

if __name__ == '__main__':
    app.run(debug=True)

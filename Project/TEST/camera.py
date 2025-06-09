from picamera2 import Picamera2
from datetime import datetime
import os
import time
import mysql.connector

def get_crop_name_from_mysql():
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',             # 실제 유저명
            password='1234',  # 비밀번호
            database='sensor'   # 데이터베이스 이름
        )
        cursor = conn.cursor()
        cursor.execute("SELECT crop FROM crop_info LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else "unknown"
    except mysql.connector.Error as err:
        print(f"MySQL 오류: {err}")
        return "unknown"

def take_photo():
    crop_name = get_crop_name_from_mysql()
    now = datetime.now()
    timestamp = now.strftime("%Y:%m:%d:%H:%M")
    filename = f"{timestamp}_{crop_name}.jpg"
    save_dir = "/home/pi/web/photos"
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(s_

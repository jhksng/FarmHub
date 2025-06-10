import subprocess
from datetime import datetime
import os
import time
import mysql.connector

# MySQL에서 작물 이름 가져오기
def get_crop_name_from_mysql():
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='1234',
            database='sensor'
        )
        cursor = conn.cursor()
        cursor.execute("SELECT crop FROM crop_info LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else "unknown"
    except mysql.connector.Error as err:
        print(f"MySQL 오류: {err}")
        return "unknown"

# 사진 촬영 함수 (fswebcam 사용)
def take_photo():
    crop_name = get_crop_name_from_mysql()
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d-%H-%M")
    filename = f"{timestamp}_{crop_name}.jpg"
    save_dir = "/home/pi/web/photos"
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, filename)

    try:
        # fswebcam으로 사진 촬영
        subprocess.run(
            ["fswebcam", "-r", "1280x720", "--no-banner", file_path],
            check=True
        )
        print(f"[✔] 사진 저장 완료: {file_path}")
    except subprocess.CalledProcessError as e:
        print(f"[✘] fswebcam 실행 오류: {e}")
    except Exception as e:
        print(f"[✘] 기타 오류: {e}")

# 메인 루프: 1시간마다 촬영 (테스트용)
if __name__ == "__main__":
    take_photo()
        

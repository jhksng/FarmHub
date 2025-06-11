import subprocess
from datetime import datetime
import os
import time
import mysql.connector

# --- 수정된 get_crop_name_from_mysql 함수 ---
def get_crop_name_from_mysql(username_to_fetch="admin"):
    """
    users 테이블에서 현재 사용자가 선택한 작물 이름을 가져옵니다.
    :param username_to_fetch: 작물 이름을 가져올 사용자의 username (기본값: 'admin').
    :return: 선택된 작물 이름 (str) 또는 'unknown' (문제가 발생했을 경우).
    """
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='1234',
            database='sensor'
        )
        cursor = conn.cursor()
        # users 테이블에서 특정 사용자가 선택한 작물 이름 (selected_crop)을 조회
        query = "SELECT selected_crop FROM users WHERE username = %s LIMIT 1"
        cursor.execute(query, (username_to_fetch,))
        result = cursor.fetchone()

        if result and result[0]:
            return result[0] # selected_crop 컬럼의 값 반환
        else:
            print(f" 사용자 '{username_to_fetch}'의 선택된 작물이 없습니다. 'unknown'으로 처리합니다.")
            return "unknown"
    except mysql.connector.Error as err:
        print(f" MySQL 오류 발생 (get_crop_name_from_mysql): {err}")
        return "unknown"
    except Exception as e:
        print(f" 기타 오류 발생 (get_crop_name_from_mysql): {e}")
        return "unknown"
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

# 사진 촬영 함수 (fswebcam 사용)
def take_photo():
    # get_crop_name_from_mysql 함수를 호출하여 작물 이름을 가져옵니다.
    # 기본적으로 'admin' 계정의 selected_crop을 가져옵니다.
    crop_name = get_crop_name_from_mysql()
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d-%H-%M")
    filename = f"{timestamp}_{crop_name}.jpg"
    save_dir = "/home/pi/web/photos"
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, filename)

    try:
        # fswebcam으로 사진 촬영
        # check=True: 명령 실행 실패 시 CalledProcessError 발생
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
    # 스크립트를 직접 실행할 때 사진 촬영
    take_photo()
    # 이 스크립트를 1시간마다 실행하려면 크론탭 설정을 해야 합니다.
    # 크론탭 예시 (매 시간 정각에 실행): 0 * * * * python3 /path/to/your/photo_script.py

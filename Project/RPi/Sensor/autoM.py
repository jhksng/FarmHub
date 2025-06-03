import RPi.GPIO as GPIO
import time
import mysql.connector

# GPIO 초기화
GPIO.setmode(GPIO.BCM)
GPIO.setup(16, GPIO.OUT)

# DB 연결
conn = mysql.connector.connect(
    host="localhost",
    user="your_user",
    password="your_password",
    database="your_db"
)
cursor = conn.cursor()

try:
    while True:
        # (1) 현재 온도를 센서에서 받아오기
        # 예시: current_temp = 센서에서 읽은 온도 값
        # 임시로 55.0을 써봅니다
        current_temp = 55.0

        # (2) DB에서 가장 최근 설정값 가져오기
        cursor.execute("SELECT target_temp FROM input ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()

        if result:
            target_temp = result[0]
            print(f"현재온도: {current_temp} / 설정온도: {target_temp}")

            if current_temp > target_temp:
                GPIO.output(16, 1)  # 쿨러 ON
                print("쿨러 ON")
            else:
                GPIO.output(16, 0)  # 쿨러 OFF
                print("쿨러 OFF")

        else:
            print("DB에 설정값이 없습니다.")

        time.sleep(5)  # 5초마다 체크

except KeyboardInterrupt:
    print("종료합니다.")
    GPIO.cleanup()

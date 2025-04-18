import time
import serial
import mysql.connector
from datetime import datetime

# MySQL/MariaDB 연결 함수
def connect_db():
    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='1234',  # 변경된 MySQL root 비밀번호
        database='data'
    )
    return conn

# 데이터베이스에 데이터 저장 함수
def save_to_db(timestamp, humidity, temperature):
    # DB 연결
    conn = connect_db()
    cursor = conn.cursor()

    # SQL 쿼리 작성
    query = "INSERT INTO SensorData (timestamp, humidity, temperature) VALUES (%s, %s, %s)"
    values = (timestamp, humidity, temperature)

    # 데이터 삽입
    cursor.execute(query, values)

    # 변경 사항 커밋
    conn.commit()

    # 연결 종료
    cursor.close()
    conn.close()

# 아두이노에서 데이터 읽고 DB에 저장하는 함수
def main():
    # 시리얼 연결 (아두이노와 연결된 포트 및 보드레이트 설정)
    ser = serial.Serial('/dev/ttyACM0', 9600, timeout=None)
    while True:
        # ser = serial.Serial('/dev/ttyACM0', 9600, timeout=None)
        # 아두이노로부터 데이터 읽기
        line = ser.readline()  # 한 줄 읽기
        arr = line.decode().strip().split(' ')  # 공백 기준으로 나누기

        # 유효한 데이터인지 확인 (빈 값이나 잘못된 값이 아니면 처리)
        if len(arr) != 2:
            continue

        # 습도와 온도 값 저장
        try:
            humidity = float(arr[0])  # 습도는 float로 변환
            temperature = float(arr[1].rstrip('\r\n'))  # 온도는 float로 변환
        except ValueError:
            # 값이 float로 변환될 수 없으면 건너뜀
            continue

        # 현재 시간 가져오기
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")  # YYYY-MM-DD HH:MM:SS 형식

        # DB에 저장
        save_to_db(timestamp, humidity, temperature)
        print(f"Saved to DB: Timestamp: {timestamp}, humidity: {humidity}, Temperature: {temperature}")
        # 10초 대기
        time.sleep(10)

if __name__ == "__main__":
    main()

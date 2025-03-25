import csv
import time
import serial
from datetime import datetime
 
def main():
  # 1) 아두이노와 시리얼 연결
# /dev/ttyACM0 부분에는 위에서 확인한 포트 번호
  # 9600 자리에는 사용하는 보드레이트를 작성한다
  ser = serial.Serial('/dev/ttyACM0', 9600, timeout=None)
  
  while True:
   # 2) 아두이노의 값 읽어옴
    line = ser.readline() # 시리얼 통신으로 값을 한 줄 읽어온다
    arr = line.decode().split(' ') # 습도, 온도를 나눠 배열에 저장
 
    # 읽은 값이 유효값이 아닐 경우 다시 읽는다
    if len(arr) != 2: 
      if float(arr[0]) < 0 or float(arr[0]) >= 100:
        continue 


    # 3) 읽은 데이터 값을 변수에 저장
# 온습도 읽기
    humidity = arr[0]
    temperature = arr[1].rstrip('\r\n')
    
    # 현재 날짜 저장
    now = datetime.now()
    month = str(now.month)
    day = str(now.day)
    hour = str(now.hour)
    min = str(now.minute) 
    nowDatetime = month+"/"+day+" "+hour+":"+min  
 
    # 4) csv 파일에 데이터 저장 
    f = open('csv 파일 이름.csv','a', newline='', encoding='utf-8')
    wr = csv.writer(f, lineterminator='\n')
    wr.writerow([nowDatetime, humidity, temperature])
    f.close()
 
    time.sleep(0.01)
    break
 
 
if __name__ == "__main__":
  main() 
# routes/camera.py

from flask import Blueprint, render_template, Response
# import cv2

camera_bp = Blueprint('camera', __name__)

# def gen_frames():
#     camera = cv2.VideoCapture(0)  # Pi Camera에 맞게 설정
#     if not camera.isOpened():
#         raise RuntimeError("카메라를 열 수 없습니다.")

#     while True:
#         success, frame = camera.read()
#         if not success:
#             break
#         else:
#             ret, buffer = cv2.imencode('.jpg', frame)
#             frame = buffer.tobytes()
#             yield (b'--frame\r\n'
#                    b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@camera_bp.route('/camera')
def camera_view():
    return render_template('camera.html')

# @camera_bp.route('/video_feed')
# def video_feed():
#     return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

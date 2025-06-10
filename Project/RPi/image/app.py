import google.generativeai as genai
from flask import Flask, request, render_template
import PIL.Image
import io

# Flask 앱 생성
app = Flask(__name__)

# 여기에 발급받은 Gemini API 키를 입력하세요.
# 보안을 위해 실제 서비스에서는 환경 변수 등을 사용하는 것이 좋습니다.
API_KEY = ''
genai.configure(api_key=API_KEY)

@app.route('/', methods=['GET', 'POST'])
def upload_and_analyze():
    if request.method == 'POST':
        # 1. 웹페이지에서 업로드한 이미지 파일 받기
        if 'crop_image' not in request.files:
            return 'No file part'
        file = request.files['crop_image']
        if file.filename == '':
            return 'No selected file'

        if file:
            # 2. 이미지를 Gemini가 인식할 수 있는 형태로 변환
            img = PIL.Image.open(file.stream)
            
            # 3. Gemini API 호출
            model = genai.GenerativeModel('gemini-pro-vision') # 이미지 분석이 가능한 모델
            
            # 💡 여기가 가장 중요한 부분! AI에게 무엇을 원하는지 명확히 지시합니다.
            prompt_text = """
            당신은 작물 분석 전문가입니다. 
            이 사진 속 작물의 종류를 알려주고, 현재 성장 단계를 상세히 분석해주세요. 
            사진을 기반으로 판단했을 때 수확이 가능한 상태인지, 
            아니라면 대략 얼마 정도 더 기다려야 하는지 예상 시기와 함께 알려주세요.
            """
            
            # 이미지와 텍스트 프롬프트를 함께 전송
            response = model.generate_content([prompt_text, img])
            
            # 4. 결과 페이지에 분석 결과 전달
            return render_template('result.html', result_text=response.text)

    # GET 요청 시 (첫 접속) 파일 업로드 페이지 보여주기
    return render_template('upload.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

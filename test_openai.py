import requests
import json
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# hospitals.constants import를 위해 현재 디렉토리를 path에 추가 (필요시)
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hospitals.constants import HOSPITAL_FIELD_DESC

# 테스트용 가짜 환경변수 설정 (실제 키가 없다면 여기에 입력하거나 실행 시 export GMS_KEY=... 해야 함)
# os.environ['GMS_KEY'] = "YOUR_API_KEY_HERE" 

# 병상/장비 코드 및 설명 매핑 (상수)

def get_recommended_fields(symptoms):
    # GMS OpenAI API 호출
    url = "https://gms.ssafy.io/gmsapi/api.openai.com/v1/chat/completions"
    
    # 환경 변수에서 키 가져오기 (없으면 에러)
    api_key = os.getenv("OPENAI_KEY") or os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("Error: API Key (GMS_KEY or OPENAI_API_KEY) not found in environment variables.")
        return {}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # 프롬프트 구성
    field_desc_str = json.dumps(HOSPITAL_FIELD_DESC, ensure_ascii=False)
    prompt = f"""
    User symptoms: {symptoms}
    
    Available Hospital Resource Fields (JSON):
    {field_desc_str}
    
    Task:
    Based on the symptoms, select the TOP 10 most critical resource fields from the list.
    Assign scores from 30 down to 12 (decreasing by 2 for each rank: 30, 28, 26... 12).
    
    Output Format:
    Return ONLY a valid JSON object where keys are the field names (e.g., 'hvec', 'hvctayn') and values are the scores (integers).
    Do not include any explanation.
    """
    
    data = {
        "model": "gpt-4o-mini", # or gpt-5-mini
        "messages": [
            {"role": "system", "content": "You are a medical assistant. Return only JSON."}, 
            {"role": "user", "content": prompt}
        ]
    }
    
    print(f"Testing OpenAI with symptoms: {symptoms}...")
    
    try:
        # verify=False는 GMS 인증서 문제 회피용
        response = requests.post(url, headers=headers, json=data, timeout=10, verify=False)
        
        if response.status_code != 200:
            print(f"API Error: {response.status_code} - {response.text}")
            return {}

        res_json = response.json()
        content = res_json['choices'][0]['message']['content']
        
        print("\n--- Raw Content ---")
        print(content)
        print("-------------------\n")
        
        # JSON 파싱 정리
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
            
        return json.loads(content)
    except Exception as e:
        print(f"Exception: {e}")
        return {}

if __name__ == "__main__":
    # 테스트할 증상
    test_symptoms = ["임산부", "만삭", "자궁출혈", "임신8개월"]
    
    result = get_recommended_fields(test_symptoms)
    
    print("\n=== Parsed Result ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))

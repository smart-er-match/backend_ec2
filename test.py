import requests
import os
from dotenv import load_dotenv
import json

load_dotenv()

def test_api():
    url = "http://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytListInfoInqire"
    api_key = os.getenv("NMC_API_KEY")

    if not api_key:
        print("Error: NMC_API_KEY not found in .env")
        return

    params = {
        "serviceKey": api_key,
        "numOfRows": 5000,
        "pageNo": 1,
        "_type": "json"
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
            if isinstance(items, dict): items = [items]
            
            print(f"Fetched {len(items)} items.")
            
            for item in items:
                addr = item.get('dutyAddr', '')
                if "전남" in addr or "전라남도" in addr:
                    print(f"[{item.get('dutyName')}] {addr}")
                    # split 결과 확인
                    parts = addr.split()
                    print(f"Split: {parts}")
                    if parts:
                        print(f"First: '{parts[0]}'")
                        
        else:
            print("API Request Failed.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_api()

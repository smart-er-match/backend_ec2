import requests
import os
from dotenv import load_dotenv
import xml.dom.minidom

load_dotenv()

def test_api():
    url = "http://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytLcinfoInqire"
    api_key = os.getenv("NMC_API_KEY")

    if not api_key:
        print("Error: NMC_API_KEY not found in .env")
        return

    # 서울 강남역, XML 요청
    params = {
        "serviceKey": api_key,
        "WGS84_LON": "127.0276", 
        "WGS84_LAT": "37.4979", 
        "numOfRows": 100,
        "pageNo": 1
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        
        print(f"Full Request URL: {response.url}")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            # XML 파싱 및 예쁘게 출력
            try:
                xml_str = response.text
                dom = xml.dom.minidom.parseString(xml_str)
                pretty_xml = dom.toprettyxml()
                
                print("\n=== FULL XML RESPONSE ===")
                print(pretty_xml)
                print("=========================\n")
                
                # totalCount 확인
                total_counts = dom.getElementsByTagName('totalCount')
                if total_counts:
                    print(f"Total Count: {total_counts[0].firstChild.data}")
                
                items = dom.getElementsByTagName('item')
                print(f"Fetched Items Tag Count: {len(items)}")

            except Exception as e:
                print(f"XML Parsing Failed: {e}")
                print(response.text)
        else:
            print("API Request Failed.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_api()
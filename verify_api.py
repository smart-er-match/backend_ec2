import requests
import json

BASE_URL = "http://localhost:8000"

def print_response(response, title):
    print(f"\n=== {title} ===")
    print(f"Status Code: {response.status_code}")
    try:
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except:
        print(response.text)

def verify_api():
    # 1. Signup
    print("\n[1] Testing Signup...")
    signup_data = {
        "username": "testuser123",
        "password": "testpassword123!",
        "email": "test@example.com",
        "name": "Test User",
        "phone_number": "010-1234-5678",
        "birth_date": "1990-01-01"
    }
    # Try to signup (might fail if already exists, which is fine for testing)
    response = requests.post(f"{BASE_URL}/accounts/signup/", data=signup_data)
    print_response(response, "Signup Result")

    # 2. Login
    print("\n[2] Testing Login...")
    login_data = {
        "username": "testuser123",
        "password": "testpassword123!"
    }
    response = requests.post(f"{BASE_URL}/accounts/login/", data=login_data)
    print_response(response, "Login Result")
    
    if response.status_code == 200:
        token = response.json().get('access')
        headers = {"Authorization": f"Bearer {token}"}
        
        # 3. General Search (Public)
        print("\n[3] Testing General Search...")
        search_data = {
            "text": "배가 너무 아파요",
            "lat": 37.5,
            "lon": 127.0
        }
        response = requests.post(f"{BASE_URL}/hospitals/search/general/", json=search_data)
        print_response(response, "General Search Result")

        # 4. Paramedic Search (Public for now, but let's test)
        print("\n[4] Testing Paramedic Search (List)...")
        response = requests.get(f"{BASE_URL}/hospitals/search/paramedic/")
        print_response(response, "Paramedic Search Result (First 2 items)")

if __name__ == "__main__":
    verify_api()

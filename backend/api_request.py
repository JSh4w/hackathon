import requests
import base64
import json
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    RAIL_EMAIL: str
    RAIL_PWORD: str
    OPENAI_API_KEY: str

    class Config:
        env_file = ".env"

settings = Settings()
email = settings.RAIL_EMAIL
password = settings.RAIL_PWORD
# Create basic auth header
credentials = base64.b64encode(f"{email}:{password}".encode()).decode()

# API endpoint and data
url = "https://hsp-prod.rockshore.net/api/v1/serviceMetrics"
headers = {
    "Authorization": f"Basic {credentials}",
    "Content-Type": "application/json"
}

data = {
    "from_loc": "BTN",
    "to_loc": "VIC",
    "from_time": "0700",
    "to_time": "0800", 
    "from_date": "2016-07-01",
    "to_date": "2016-08-01",
    "days": "WEEKDAY"
}

try:
    print("Attempting connection to HSP API...")
    response = requests.post(url, headers=headers, json=data, timeout=60)
    print(f"✅ Success! Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Services found: {len(data.get('Services', []))}")
        print("\n" + "="*50)
        print("FULL JSON RESPONSE:")
        print("="*50)
        print(json.dumps(data, indent=2))
    else:
        print(f"Response: {response.text}")
except requests.exceptions.Timeout:
    print("❌ Timeout - HSP API server appears to be down or very slow")
    print("This commonly happens during overnight maintenance windows")
except requests.exceptions.ConnectionError:
    print("❌ Connection Error - Cannot reach HSP API server")
    print("Check your internet connection or the server may be down")
except Exception as e:
    print(f"❌ Unexpected Error: {e}")

input("Press Enter to continue...")
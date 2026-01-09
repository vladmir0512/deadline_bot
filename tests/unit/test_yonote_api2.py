import requests
import time
from dotenv import load_dotenv
load_dotenv()
import os

YONOTE_API_KEY = os.getenv('YONOTE_API_KEY')
YONOTE_CALENDAR_ID = os.getenv('YONOTE_CALENDAR_ID')

print("Testing different approaches...")

# Попробуем разные URL для получения файла
test_urls = [
    'https://app.yonote.ru/api/database.export_csv',
    'https://unikeygroup.yonote.ru/api/database.export_csv',
]

for url in test_urls:
    print(f"\nTrying URL: {url}")
    params = {'id': YONOTE_CALENDAR_ID, 'token': YONOTE_API_KEY}
    response = requests.get(url, params=params, timeout=10)

    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        try:
            data = response.json()
            print("JSON response detected")
            print("Keys:", list(data.keys()) if isinstance(data, dict) else "Not dict")

            if 'data' in data and 'fileOperation' in data['data']:
                operation = data['data']['fileOperation']
                print(f"Operation ID: {operation['id']}")
                print(f"State: {operation['state']}")

                # Если операция завершена, попробуем скачать
                if operation['state'] == 'complete' and 'url' in operation:
                    file_url = operation['url']
                    print(f"Downloading from: {file_url}")
                    file_response = requests.get(file_url, timeout=10)
                    print(f"File status: {file_response.status_code}")
                    if file_response.status_code == 200:
                        print(f"File size: {len(file_response.text)} chars")
                        print("First 200 chars:", repr(file_response.text[:200]))
                    break
                else:
                    print("Operation not complete or no URL")
            else:
                print("Response:", data)
        except:
            # Возможно это уже CSV файл
            print("Response looks like CSV:")
            print("Length:", len(response.text))
            print("First 200 chars:", repr(response.text[:200]))
            if len(response.text) > 100:
                print("SUCCESS: Got CSV data!")
                break
    else:
        print("Error:", response.text[:200])

# Попробуем подождать и повторить запрос
print("\nTrying with delay...")
time.sleep(5)
params = {'id': YONOTE_CALENDAR_ID, 'token': YONOTE_API_KEY}
response = requests.get('https://app.yonote.ru/api/database.export_csv', params=params, timeout=10)
print(f"After delay - Status: {response.status_code}")
if response.status_code == 200:
    if response.text.startswith('{'):
        print("Still JSON response")
    else:
        print("Got CSV! Length:", len(response.text))
        print("First 200 chars:", repr(response.text[:200]))

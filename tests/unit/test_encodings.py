import requests
from dotenv import load_dotenv
load_dotenv()
import os

# Тестируем разные кодировки
calendar_id = os.getenv('YONOTE_CALENDAR_ID')
api_key = os.getenv('YONOTE_API_KEY')

params = {
    'filter': '{"parentDocumentId": "' + calendar_id + '"}',
    'limit': '1',
    'offset': '0',
    'sort': '["tableOrder","ASC"]',
    'userTimeZone': 'Europe/Moscow',
}

url = 'https://unikeygroup.yonote.ru/api/v2/database/rows'
headers = {
    'Authorization': f'Bearer {api_key}',
}

response = requests.get(url, headers=headers, params=params)

if response.status_code == 200:
    print('Raw bytes:', response.content[:100])
    print()

    # Тестируем разные кодировки
    encodings = ['utf-8', 'cp1251', 'windows-1251', 'iso-8859-5', 'koi8-r', 'cp866', 'mac_cyrillic']

    for enc in encodings:
        try:
            decoded = response.content.decode(enc, errors='replace')
            if 'Общий' in decoded or ('{' in decoded and '}' in decoded):
                print(f'{enc}: {repr(decoded[:80])}')
                if 'Общий' in decoded:
                    print(f'*** {enc} WORKS! ***')
                    break
        except Exception as e:
            print(f'{enc}: ERROR - {e}')

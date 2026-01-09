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
    'Accept': 'application/json',
    'Authorization': f'Bearer {api_key}',
}

response = requests.get(url, headers=headers, params=params)

print('Raw bytes preview:', response.content[:200])
print()

# Пробуем разные кодировки
encodings = ['utf-8', 'cp1251', 'windows-1251', 'iso-8859-5', 'koi8-r', 'cp866']
for enc in encodings:
    try:
        decoded = response.content.decode(enc, errors='replace')
        print(f'{enc}: {repr(decoded[:100])}')
        if 'Общий' in decoded or '�����' not in decoded[:50]:  # Ищем правильную кириллицу
            print(f'*** {enc} WORKS! ***')
            break
    except Exception as e:
        print(f'{enc}: ERROR - {e}')

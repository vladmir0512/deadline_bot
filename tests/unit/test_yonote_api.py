import requests
import time
from dotenv import load_dotenv
load_dotenv()
import os

YONOTE_API_KEY = os.getenv('YONOTE_API_KEY')
YONOTE_CALENDAR_ID = os.getenv('YONOTE_CALENDAR_ID')

# Шаг 1: Запускаем экспорт
params = {'id': YONOTE_CALENDAR_ID, 'token': YONOTE_API_KEY}
response = requests.get('https://app.yonote.ru/api/database.export_csv', params=params, timeout=10)

if response.status_code == 200:
    data = response.json()
    operation_id = data['data']['fileOperation']['id']
    print(f'Started export operation: {operation_id}')

    # Шаг 2: Ждем завершения операции
    for i in range(30):  # Ждем максимум 30 секунд
        time.sleep(1)

        # Проверяем статус операции
        status_url = f'https://app.yonote.ru/api/fileOperations/{operation_id}'
        status_response = requests.get(status_url, params={'token': YONOTE_API_KEY}, timeout=10)

        if status_response.status_code == 200:
            status_data = status_response.json()
            state = status_data['data']['state']
            print(f'Operation state: {state}')

            if state == 'complete':
                # Получаем URL файла
                file_url = status_data['data'].get('url')
                if file_url:
                    print(f'Downloading file from: {file_url}')
                    file_response = requests.get(file_url, timeout=10)
                    print(f'File downloaded, size: {len(file_response.text)} chars')
                    print('First 200 chars:', repr(file_response.text[:200]))
                else:
                    print('No URL in completed operation')
                    print('Full status data:', status_data)
                break
            elif state == 'error':
                print('Export failed:', status_data['data'].get('error'))
                print('Full status data:', status_data)
                break
        else:
            print(f'Status check failed: {status_response.status_code}')
            print('Response:', status_response.text)
else:
    print('Export start failed:', response.text)

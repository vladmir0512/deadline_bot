"""
Скрипт для проверки пользователей в Yonote API.
"""
import os
from dotenv import load_dotenv
load_dotenv()
import requests
import json

YONOTE_BASE_URL = 'https://unikeygroup.yonote.ru/api/v2'
YONOTE_API_KEY = os.getenv('YONOTE_API_KEY')

def get_yonote_users():
    """Получаем информацию о пользователях из Yonote"""
    url = f"{YONOTE_BASE_URL}/users"
    headers = {
        "Authorization": f"Bearer {YONOTE_API_KEY}",
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        raw_text = response.content.decode('utf-8', errors='replace')
        data = json.loads(raw_text)

        print("Пользователи Yonote:")
        if isinstance(data, list):
            for user in data:
                user_id = user.get('id')
                username = user.get('username') or user.get('name') or user.get('email')
                print(f"  ID: {user_id}, Username: {username}")
        else:
            print(f"Неожиданный формат данных: {json.dumps(data, indent=2, ensure_ascii=False)}")
    else:
        print(f"Ошибка API: {response.status_code} - {response.text}")

def get_workspace_users():
    """Получаем пользователей рабочего пространства"""
    url = f"{YONOTE_BASE_URL}/workspace/users"
    headers = {
        "Authorization": f"Bearer {YONOTE_API_KEY}",
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        raw_text = response.content.decode('utf-8', errors='replace')
        data = json.loads(raw_text)

        print("\nПользователи рабочего пространства:")
        if isinstance(data, dict) and 'data' in data:
            users = data['data']
            if isinstance(users, list):
                for user in users:
                    user_id = user.get('id')
                    name = user.get('name')
                    email = user.get('email')
                    username = user.get('username')
                    print(f"  ID: {user_id}, Name: {name}, Email: {email}, Username: {username}")
            else:
                print(f"Неожиданный формат: {type(users)}")
        else:
            print(f"Неожиданный формат данных: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}...")
    else:
        print(f"Ошибка API: {response.status_code} - {response.text}")

if __name__ == "__main__":
    get_yonote_users()
    get_workspace_users()

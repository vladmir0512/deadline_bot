import aiohttp
import json
import requests
from dotenv import load_dotenv
load_dotenv()
import os
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict

YONOTE_BASE_URL = 'https://unikeygroup.yonote.ru/api/v2'
YONOTE_API_KEY = os.getenv('YONOTE_API_KEY')
YONOTE_CALENDAR_ID = os.getenv('YONOTE_CALENDAR_ID')

# Кэш для соответствия Yonote user ID -> username
_yonote_user_cache: Dict[str, str] = {}

def _get_yonote_users() -> Dict[str, str]:
    """Получаем словарь Yonote user ID -> username"""
    global _yonote_user_cache

    if _yonote_user_cache:
        return _yonote_user_cache

    url = f"{YONOTE_BASE_URL}/users"
    headers = {
        "Authorization": f"Bearer {YONOTE_API_KEY}",
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            raw_text = response.content.decode('utf-8', errors='replace')
            data = json.loads(raw_text)

            if isinstance(data, dict) and 'data' in data:
                users = data['data']
                if isinstance(users, list):
                    for user in users:
                        user_id = user.get('id')
                        username = user.get('name')  # Используем name как username
                        if user_id and username:
                            _yonote_user_cache[user_id] = username

        return _yonote_user_cache
    except Exception as e:
        print(f"Ошибка при получении пользователей Yonote: {e}")
        return {}

@dataclass
class YonoteDeadline:
    id: str
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    status: Optional[str] = None
    assignee: Optional[str] = None
    tags: List[str] = None
    raw_data: Optional[dict] = None
    user_identifier: Optional[str] = None  # Теперь будет список пользователей через запятую

    def __post_init__(self):
        if self.tags is None:
            self.tags = []

async def fetch_user_deadlines(user_identifier=None):
    """Получаем дедлайны из Yonote через v2 API"""
    filter_obj = {"parentDocumentId": YONOTE_CALENDAR_ID}

    params = {
        "filter": json.dumps(filter_obj, ensure_ascii=False),
        "limit": "100",
        "offset": "0",
        "sort": '[["tableOrder","ASC"]]',
        "userTimeZone": "Europe/Moscow",
    }

    url = YONOTE_BASE_URL.rstrip("/") + "/database/rows"
    headers = {
        "Authorization": f"Bearer {YONOTE_API_KEY}",
    }

    # Используем requests с правильным декодированием
    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        # Данные приходят в UTF-8 байтах, декодируем правильно
        raw_text = response.content.decode('utf-8', errors='replace')
        data = json.loads(raw_text)
        rows = data.get("data", [])

        # Получаем соответствие user ID -> username
        yonote_users = _get_yonote_users()

        deadlines = []
        for row in rows:
            title = row.get("title", "")
            description = row.get("text", "")
            values = row.get("values", {})

            deadline = YonoteDeadline(
                id=str(row.get("id", "")),
                title=title,
                description=description,
                raw_data=row
            )

            # Парсим дату из values
            for field_id, field_data in values.items():
                if isinstance(field_data, dict) and "from" in field_data:
                    date_str = field_data.get("from")
                    if date_str:
                        try:
                            deadline.due_date = datetime.strptime(date_str, "%Y-%m-%d")
                        except ValueError:
                            # Пробуем другие форматы даты
                            try:
                                deadline.due_date = datetime.strptime(date_str, "%Y/%m/%d")
                            except ValueError:
                                pass

            # Парсим назначенных пользователей
            assigned_users = []
            for field_id, field_data in values.items():
                if isinstance(field_data, list):
                    # Это поле с пользователями - список user ID
                    for user_id in field_data:
                        if user_id in yonote_users:
                            assigned_users.append(yonote_users[user_id])

            # Сохраняем список назначенных пользователей
            deadline.user_identifier = ", ".join(assigned_users) if assigned_users else None

            # Фильтруем по user_identifier, если указан
            if user_identifier:
                # Если дедлайн не назначен этому пользователю, пропускаем
                if not assigned_users or user_identifier not in assigned_users:
                    continue

            deadlines.append(deadline)

        return deadlines
    else:
        print(f"Yonote API error: {response.status_code} - {response.text}")
        # В случае ошибки возвращаем пустой список
        return []

"""
Скрипт для отладки данных из Yonote API.
"""
import os
from dotenv import load_dotenv
load_dotenv()
import requests
import json

YONOTE_BASE_URL = 'https://unikeygroup.yonote.ru/api/v2'
YONOTE_API_KEY = os.getenv('YONOTE_API_KEY')
YONOTE_CALENDAR_ID = os.getenv('YONOTE_CALENDAR_ID')

def debug_yonote_data():
    """Получаем и анализируем данные из Yonote"""
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

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        raw_text = response.content.decode('utf-8', errors='replace')
        data = json.loads(raw_text)
        rows = data.get("data", [])

        print(f"Всего записей: {len(rows)}")
        print("\n" + "="*50)

        for i, row in enumerate(rows[:5]):  # Показываем первые 5 записей
            print(f"\nЗапись {i+1}:")
            print(f"ID: {row.get('id')}")
            print(f"Title: {row.get('title')}")
            print(f"Text: {row.get('text')}")

            values = row.get("values", {})
            print(f"Values: {json.dumps(values, indent=2, ensure_ascii=False)}")

            print("-" * 30)

        # Анализируем структуру values для поиска полей с пользователями
        if rows:
            all_value_keys = set()
            for row in rows:
                values = row.get("values", {})
                all_value_keys.update(values.keys())

            print(f"\nВсе ключи в values: {sorted(all_value_keys)}")

            # Проверяем, какие поля содержат информацию о пользователях
            for key in sorted(all_value_keys):
                print(f"\nАнализ поля '{key}':")
                unique_values = set()
                for row in rows:
                    values = row.get("values", {})
                    if key in values:
                        val = values[key]
                        if isinstance(val, dict):
                            unique_values.add(json.dumps(val, sort_keys=True))
                        else:
                            unique_values.add(str(val))

                print(f"Уникальные значения ({len(unique_values)}):")
                for val in list(unique_values)[:3]:  # Показываем первые 3 уникальных значения
                    print(f"  {val}")

    else:
        print(f"Ошибка API: {response.status_code} - {response.text}")

if __name__ == "__main__":
    debug_yonote_data()

"""
Модуль для работы с Yonote через CSV экспорт API.

Более надежный способ получения данных, особенно для полей типа "люди".
"""

from __future__ import annotations

import asyncio
import csv
import io
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Iterable

import aiohttp
from dotenv import load_dotenv

# Подгружаем переменные окружения из .env
load_dotenv()

YONOTE_API_KEY = os.getenv("YONOTE_API_KEY")
YONOTE_CALENDAR_ID = os.getenv("YONOTE_CALENDAR_ID")

@dataclass
class YonoteDeadline:
    """Упрощённая внутренняя модель дедлайна, полученного из Yonote."""
    
    id: str  # Уникальный ID
    title: str
    description: Optional[str]
    due_date: Optional[datetime]
    user_identifier: Optional[str]  # Список людей через запятую
    source: str = "yonote_csv"


def parse_datetime(value: str) -> Optional[datetime]:
    """Парсит дату из строки в datetime."""
    if not value:
        return None
    try:
        # CSV API возвращает даты в формате ISO 8601
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        # Убедимся, что дата имеет timezone info
        if result.tzinfo is None:
            from datetime import timezone
            result = result.replace(tzinfo=timezone.utc)
        return result
    except ValueError:
        # Если не удается распознать формат даты
        print(f"[CSV Yonote] Ошибка парсинга даты '{value}'")
        return None


class YonoteCsvClient:
    """Клиент для работы с Yonote через CSV экспорт API."""
    
    def __init__(self, api_key: str | None = None, calendar_id: str | None = None):
        self.api_key = api_key or YONOTE_API_KEY
        self.calendar_id = calendar_id or YONOTE_CALENDAR_ID
        
        if not self.api_key or not self.calendar_id:
            raise ValueError("YONOTE_API_KEY и YONOTE_CALENDAR_ID должны быть заданы")
    
    async def fetch_deadlines_raw_csv(self) -> str:
        """Получить сырой CSV с дедлайнами."""
        csv_url = "https://app.yonote.ru/api/database.export_csv"
        
        params = {
            "databaseId": self.calendar_id,
            "token": self.api_key
        }
        
        print(f"[CSV Yonote] Запрос CSV по адресу: {csv_url}")
        print(f"[CSV Yonote] Параметры: {params}")
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(csv_url, params=params) as resp:
                    print(f"[CSV Yonote] Статус ответа: {resp.status}")
                    if resp.status == 200:
                        csv_content = await resp.text()
                        print(f"[CSV Yonote] Получено {len(csv_content)} символов CSV")
                        return csv_content
                    else:
                        text = await resp.text()
                        print(f"[CSV Yonote] Ошибка {resp.status}: {text}")
                        raise Exception(f"Ошибка при получении CSV: {resp.status} - {text}")
            except Exception as e:
                print(f"[CSV Yonote] Исключение при запросе: {e}")
                raise
    
    def parse_csv_to_deadlines(self, csv_content: str) -> List[YonoteDeadline]:
        """Парсит CSV содержимое в список дедлайнов."""
        # CSV содержит BOM в начале, нужно его обработать
        if csv_content.startswith('\ufeff'):
            csv_content = csv_content[1:]  # Удаляем BOM
        
        # Разбиваем на строки и обрабатываем
        csv_io = io.StringIO(csv_content)
        
        # Читаем первую строку, чтобы определить структуру
        first_line = csv_io.readline()
        if not first_line.strip():
            print("[CSV Yonote] Пустой CSV файл")
            return []
        
        # Возвращаемся к началу и читаем как CSV
        csv_io.seek(0)
        reader = csv.reader(csv_io, delimiter=';', quotechar='"')
        
        # Чтение заголовков
        headers = next(reader, None)
        if not headers:
            print("[CSV Yonote] Нет заголовков в CSV")
            return []
        
        print(f"[CSV Yonote] Найдены заголовки: {headers}")
        
        # Определяем индексы столбцов
        title_idx = None
        people_idx = None
        song_idx = None  # или description
        date_idx = None
        
        for i, header in enumerate(headers):
            header_lower = header.lower()
            if any(keyword in header_lower for keyword in ["название", "title", "name"]):
                title_idx = i
            elif any(keyword in header_lower for keyword in ["люди", "people", "person", "участник", "member", "assignee"]):
                people_idx = i
            elif any(keyword in header_lower for keyword in ["песня", "song", "description", "текст"]):
                song_idx = i
            elif any(keyword in header_lower for keyword in ["дата", "date", "due", "deadline", "end", "start"]):
                date_idx = i
        
        if title_idx is None:
            print(f"[CSV Yonote] Не найден столбец с названиями: {headers}")
            return []
        
        # Проверяем, что дедлайны есть
        deadlines = []
        for row_num, row in enumerate(reader, start=2):  # начинаем с 2, т.к. 1 - заголовки
            if len(row) <= title_idx:
                print(f"[CSV Yonote] Строка {row_num} слишком короткая, пропуск")
                continue
            
            title = row[title_idx].strip() if title_idx < len(row) else ""
            if not title or title in ["", ";", ";;", ";;;"]:  # Пустая строка или заголовки
                continue
            
            # Получаем остальные поля
            people = row[people_idx].strip() if people_idx is not None and people_idx < len(row) else None
            song_desc = row[song_idx].strip() if song_idx is not None and song_idx < len(row) else None
            date_str = row[date_idx].strip() if date_idx is not None and date_idx < len(row) else None
            
            # Парсим дату
            due_date = parse_datetime(date_str) if date_str else None
            
            # Создаем уникальный ID на основе заголовка и даты (для совместимости с существующей системой)
            id_suffix = str(hash(title + (date_str or "")))[:8]
            
            deadline = YonoteDeadline(
                id=f"csv_{id_suffix}",
                title=title,
                description=song_desc,
                due_date=due_date,
                user_identifier=people
            )
            
            deadlines.append(deadline)
            print(f"[CSV Yonote] Обработан дедлайн #{len(deadlines)}: '{title}', люди: {people}, дата: {due_date}")
        
        print(f"[CSV Yonote] Всего обработано {len(deadlines)} дедлайнов из CSV")
        return deadlines

    def filter_deadlines_by_user(
        self,
        deadlines: Iterable[YonoteDeadline],
        *,
        user_identifier: str | None,
    ) -> List[YonoteDeadline]:
        """
        Отфильтровать дедлайны по пользователю (email/ник).
        Если user_identifier не задан — возвращаем всё как есть.

        Учитывает, что в user_identifier может быть несколько людей через запятую.
        """
        if not user_identifier:
            return list(deadlines)

        target = user_identifier.strip().lower()
        result: list[YonoteDeadline] = []
        for d in deadlines:
            if not d.user_identifier:
                continue

            # Если в дедлайне несколько людей через запятую, проверяем каждого
            deadline_people = [p.strip().lower() for p in d.user_identifier.split(",")]

            # Проверяем точное совпадение или вхождение в список людей
            if target in deadline_people:
                result.append(d)
                print(f"[CSV Yonote] Дедлайн '{d.title}' соответствует пользователю '{target}'")

        print(f"[CSV Yonote] Отфильтровано {len(result)} дедлайнов из {len(list(deadlines))} для пользователя '{target}'")
        return result


async def fetch_csv_user_deadlines(user_identifier: str | None = None) -> List[YonoteDeadline]:
    """
    Вспомогательная высокоуровневая функция для получения дедлайнов через CSV API:
    - делает запрос к Yonote CSV API
    - парсит дедлайны
    - фильтрует по пользователю (если указан)
    """
    print(f"[CSV Yonote] Запрашиваю дедлайны для пользователя: {user_identifier}")
    
    client = YonoteCsvClient()
    
    # Получаем сырой CSV
    csv_content = await client.fetch_deadlines_raw_csv()
    
    # Парсим в дедлайны
    parsed = client.parse_csv_to_deadlines(csv_content)
    
    # Фильтруем (если указан пользователь)
    if user_identifier:
        return client.filter_deadlines_by_user(parsed, user_identifier=user_identifier)
    else:
        return parsed


if __name__ == "__main__":
    # Тестирование CSV API
    async def test_csv_api():
        print("=== Тестирование CSV API ===")
        
        # Тестируем без фильтра
        print("\n1. Тестируем получение всех дедлайнов:")
        all_deadlines = await fetch_csv_user_deadlines(None)
        print(f"Всего дедлайнов: {len(all_deadlines)}")
        for d in all_deadlines:
            print(f"  - {d.title} | Люди: {d.user_identifier} | Дата: {d.due_date}")
        
        # Тестируем с фильтрацией по VJ_Games
        print(f"\n2. Тестируем поиск дедлайнов для 'VJ_Games':")
        vj_deadlines = await fetch_csv_user_deadlines("VJ_Games")
        print(f"Дедлайнов для 'VJ_Games': {len(vj_deadlines)}")
        for d in vj_deadlines:
            print(f"  - {d.title} | Люди: {d.user_identifier} | Дата: {d.due_date}")
        
        # Тестируем с фильтрацией по ArAhis
        print(f"\n3. Тестируем поиск дедлайнов для 'ArAhis':")
        arahis_deadlines = await fetch_csv_user_deadlines("ArAhis")
        print(f"Дедлайнов для 'ArAhis': {len(arahis_deadlines)}")
        for d in arahis_deadlines:
            print(f"  - {d.title} | Люди: {d.user_identifier} | Дата: {d.due_date}")
    
    # Запускаем тест
    asyncio.run(test_csv_api())
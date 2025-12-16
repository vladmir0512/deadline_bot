"""
Клиент для работы с Yonote API.

Предполагаем базовый формат API (так как точной публичной спецификации нет):
- Базовый URL берём из переменной окружения YONOTE_BASE_URL
- Авторизация через заголовок X-API-Key с ключом YONOTE_API_KEY

Основная задача на этом этапе — получить «сырой» список дедлайнов
и привести их к удобному внутреннему виду.
"""

from __future__ import annotations

import asyncio
import csv
import io
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, List, Optional

import aiohttp
from dotenv import load_dotenv


# Подгружаем переменные окружения из .env при импорте модуля
load_dotenv()

# Yonote может работать в двух режимах:
# 1) RPC-методы вида https://app.yonote.ru/api/<method_name>
# 2) REST-подобный v2 API вида https://<tenant>.yonote.ru/api/v2/database/rows
# 3) CSV экспорт API для получения данных с лучшей структурой
#
# Для работы с календарём/базой сейчас используем CSV export API,
# поскольку он лучше отображает информацию о назначенных пользователях.
YONOTE_API_KEY = os.getenv("YONOTE_API_KEY")  # используется как токен для CSV экспорт
YONOTE_CALENDAR_ID = os.getenv("YONOTE_CALENDAR_ID")
YONOTE_TIMEZONE = os.getenv("YONOTE_TIMEZONE", "Europe/Moscow")
YONOTE_BASE_URL = os.getenv("YONOTE_BASE_URL", "https://unikeygroup.yonote.ru/api/v2")  # резервный v2 API


class YonoteClientError(Exception):
    """Базовая ошибка клиента Yonote."""


class YonoteAuthError(YonoteClientError):
    """Ошибка аутентификации в Yonote."""


class YonoteServerError(YonoteClientError):
    """Ошибка на стороне сервера Yonote."""


@dataclass
class YonoteDeadline:
    """Упрощённая внутренняя модель дедлайна, полученного из Yonote."""

    id: str
    title: str
    description: Optional[str]
    due_date: Optional[datetime]
    user_identifier: Optional[str]
    source: str = "yonote"


class YonoteClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, *, timeout: int = 10) -> None:
        self.base_url = base_url or YONOTE_BASE_URL
        self.api_key = api_key or YONOTE_API_KEY
        self.calendar_id = os.getenv("YONOTE_CALENDAR_ID")
        if not self.api_key:
            raise YonoteAuthError("YONOTE_API_KEY (token) не задан в окружении или не передан в YonoteClient")
        if not self.calendar_id:
            raise YonoteAuthError("YONOTE_CALENDAR_ID не задан в окружении")

        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def _call_method(
        self,
        method_name: str,
        *,
        payload: dict[str, Any] | None = None,
        retries: int = 3,
        retry_delay: float = 1.0,
    ) -> Any:
        """
        Вызов RPC-метода Yonote:
        POST https://app.yonote.ru/api/<method_name>
        с заголовками:
          - Content-Type: application/json
          - Accept: application/json

        Токен передаётся в теле запроса, как в примерах Yonote:
        {
          "token": "...",
          ...
        }
        """
        url = self.base_url.rstrip("/") + "/" + method_name.lstrip("/")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                body = dict(payload or {})
                # не перетираем token, если вдруг явно передали в payload
                body.setdefault("token", self.api_key)

                # Простой подробный лог запроса
                print(f"[Yonote] Attempt {attempt}/{retries}")
                print(f"[Yonote] URL: {url}")
                print(f"[Yonote] Headers: {{'Accept': 'application/json', 'Content-Type': 'application/json'}}")
                print(f"[Yonote] Payload: {body}")

                async with aiohttp.ClientSession(timeout=self._timeout) as session:
                    async with session.post(url, headers=headers, json=body) as resp:
                        print(f"[Yonote] Response status: {resp.status}")
                        if resp.status == 401 or resp.status == 403:
                            text = await resp.text()
                            print(f"[Yonote] Auth error body: {text}")
                            raise YonoteAuthError(f"Ошибка аутентификации Yonote (status={resp.status})")
                        if 500 <= resp.status < 600:
                            text = await resp.text()
                            print(f"[Yonote] Server error body: {text}")
                            raise YonoteServerError(f"Ошибка сервера Yonote (status={resp.status})")
                        if resp.status >= 400:
                            text = await resp.text()
                            print(f"[Yonote] Client error body: {text}")
                            raise YonoteClientError(f"Ошибка запроса к Yonote (status={resp.status}, body={text})")

                        # Пробуем распарсить JSON и залогировать укороченную версию
                        data = await resp.json()
                        preview = str(data)
                        if len(preview) > 500:
                            preview = preview[:500] + "...[truncated]"
                        print(f"[Yonote] JSON response preview: {preview}")
                        return data
            except (YonoteClientError, YonoteAuthError, YonoteServerError) as e:
                # наши «логические» ошибки — не всегда имеет смысл ретраить, но пока просто пробрасываем
                last_error = e
                break
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                # сетевые ошибки/таймауты — пробуем ещё раз
                last_error = e
                if attempt >= retries:
                    break
                await asyncio.sleep(retry_delay)

        assert last_error is not None
        raise last_error

    async def fetch_deadlines_raw(self, *, user: str | None = None) -> Any:
        """
        Получить «сырые» строки базы (rows) из Yonote через v2 API.

        Используем GET-запрос вида:
        https://<tenant>.yonote.ru/api/v2/database/rows?filter={...}&limit=100&offset=0&sort=...&userTimeZone=...

        Авторизация:
        - заголовок Authorization: Bearer <YONOTE_API_KEY>
        """
        if not YONOTE_CALENDAR_ID:
            raise YonoteClientError("YONOTE_CALENDAR_ID (parentDocumentId) не задан в окружении")

        filter_obj = {"parentDocumentId": YONOTE_CALENDAR_ID}

        import json

        params = {
            "filter": json.dumps(filter_obj, ensure_ascii=False),
            "limit": "100",
            "offset": "0",
            "sort": '[["tableOrder","ASC"]]',
            "userTimeZone": YONOTE_TIMEZONE,
        }

        url = self.base_url.rstrip("/") + "/database/rows"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        print("[Yonote v2] URL:", url)
        print("[Yonote v2] Params:", params)
        print("[Yonote v2] Headers: {'Accept': 'application/json', 'Authorization': 'Bearer ***'}")

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.get(url, headers=headers, params=params) as resp:
                print("[Yonote v2] Response status:", resp.status)
                text = await resp.text()
                preview_limit = 3000
                print("[Yonote v2] Raw body preview:", text[:preview_limit] + ("...[truncated]" if len(text) > preview_limit else ""))

                if resp.status == 401 or resp.status == 403:
                    raise YonoteAuthError(f"Ошибка аутентификации Yonote (status={resp.status})")
                if resp.status >= 400:
                    raise YonoteClientError(f"Ошибка запроса к Yonote v2 (status={resp.status}, body={text})")

                return await resp.json()

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, (int, float)):
            # timestamp - создаем timezone-aware datetime
            from datetime import UTC
            return datetime.fromtimestamp(value, tz=UTC)
        if isinstance(value, str):
            # Очищаем строку от лишних пробелов
            value = value.strip()
            # Пробуем стандартный ISO формат
            try:
                # Если есть Z или +, используем fromisoformat
                if "Z" in value or "+" in value or value.count("-") >= 2:
                    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    # Если datetime без timezone, добавляем UTC
                    if dt.tzinfo is None:
                        from datetime import UTC
                        dt = dt.replace(tzinfo=UTC)
                    return dt
                # Если формат YYYY-MM-DD или YYYY/MM/DD
                elif "/" in value or (value.count("-") == 2 and len(value) == 10):
                    # Заменяем / на - для единообразия
                    date_str = value.replace("/", "-")
                    # Парсим дату без времени
                    from datetime import UTC
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    # Добавляем timezone UTC
                    return dt.replace(tzinfo=UTC)
            except (ValueError, AttributeError) as e:
                print(f"[Yonote] Ошибка парсинга даты '{value}': {e}")
                return None
        return None

    def parse_deadlines(self, raw: Any) -> List[YonoteDeadline]:
        """
        Преобразовать ответ Yonote в список YonoteDeadline.

        Для v2 rows API формат примерно такой:
        {
          "total": 6,
          "data": [
            {
              "id": "...",
              "title": "...",
              "url": "/doc/...",
              "type": "row",
              "properties": {...},
              "values": {...}
            },
            ...
          ]
        }

        Пока что берём из строки только id и title, а due_date и user_identifier
        оставляем пустыми. Позже можно будет привязать конкретные свойства
        (из values) к дате и пользователю.
        """
        results: list[YonoteDeadline] = []

        # Если это обёртка v2 с полем data
        if isinstance(raw, dict) and "data" in raw and isinstance(raw["data"], list):
            items = raw["data"]
        # Старый вариант: просто список элементов
        elif isinstance(raw, Iterable):
            items = raw
        else:
            return results

        # Определяем ID свойства «люди» и «дата» автоматически из properties
        # Проверяем несколько элементов для более точного определения типов полей
        people_prop_id = None
        date_prop_id = None

        # Проверяем несколько элементов для более точного определения типов полей
        sample_items = items[:3] if isinstance(items, list) and len(items) >= 3 else items if isinstance(items, list) else [items] if items else []

        # Сначала ищем в properties
        for item in sample_items:
            if isinstance(item, dict):
                properties = item.get("properties") or {}
                for prop_id, prop_data in properties.items():
                    if isinstance(prop_data, dict):
                        prop_name = prop_data.get("name", "").lower()
                        prop_type = prop_data.get("type") or prop_data.get("property_type")

                        # Проверяем по типу поля
                        if prop_type in ["people", "person", "personList"]:
                            people_prop_id = prop_id
                            print(f"[Yonote] Найдено поле типа 'Люди' в properties: {prop_id} (type: {prop_type}, name: {prop_data.get('name', 'Unknown')})")
                        elif prop_type in ["date", "datetime", "dateRange", "dateTime"]:
                            date_prop_id = prop_id
                            print(f"[Yonote] Найдено поле типа 'Дата' в properties: {prop_id} (type: {prop_type})")

                        # Также проверяем по названию поля (на случай, если тип не определен корректно)
                        if not people_prop_id and any(keyword in prop_name for keyword in ["люди", "людей", "people", "person", "участники", "участник", "member", "members", "назначен", "assignee", "assigned", "responsible"]):
                            people_prop_id = prop_id
                            print(f"[Yonote] Найдено потенциальное поле 'Люди' по названию: {prop_id} (name: {prop_name}, type: {prop_type})")

        # Если не нашли в properties, пробуем найти по структуре values в нескольких элементах
        if not people_prop_id:
            # Собираем все возможные поля values из нескольких элементов
            potential_people_fields = {}

            for item in sample_items:
                if isinstance(item, dict):
                    values = item.get("values") or {}
                    if isinstance(values, dict):
                        for key, val in values.items():
                            # Если поле встречается часто и выглядит как список пользователей
                            if key not in potential_people_fields:
                                potential_people_fields[key] = {"count": 0, "examples": []}

                            potential_people_fields[key]["count"] += 1

                            if len(potential_people_fields[key]["examples"]) < 3:  # Сохраняем до 3 примеров
                                potential_people_fields[key]["examples"].append(val)

                            # Проверяем, похоже ли значение на поле "люди" по структуре
                            if isinstance(val, list) and val:
                                first = val[0] if val else None
                                if isinstance(first, dict) and ("label" in first or "id" in first or "name" in first):
                                    # Похоже на структуру поля «люди»
                                    people_prop_id = key
                                    print(f"[Yonote] Найдено поле 'люди' по структуре списка: {key}")
                                    break
                            # Также проверяем, может быть люди хранятся как строка с разделением
                            elif isinstance(val, str) and ("," in val or "@" in val):
                                # Вероятно, это поле с людьми (если содержит email или список имен)
                                people_prop_id = key
                                print(f"[Yonote] Найдено поле 'люди' как строка с разделителями: {key}")
                                break
                            # Также проверим на UUID-подобные строки в списках
                            elif isinstance(val, list) and val and all(isinstance(item, str) and len(item) == 36 and item.count('-') == 4 for item in val):
                                # Выглядит как список UUID пользователей
                                people_prop_id = key
                                print(f"[Yonote] Найдено поле 'люди' как список UUID: {key}")
                                break

                        if people_prop_id:  # Если уже нашли, выходим из цикла
                            break

            # Если все еще не нашли, но есть потенциальные кандидаты, проверим их
            if not people_prop_id and potential_people_fields:
                # Сортируем потенциальные поля по частоте появления
                sorted_candidates = sorted(potential_people_fields.items(), key=lambda x: x[1]["count"], reverse=True)

                for candidate_id, candidate_info in sorted_candidates[:3]:  # Проверяем топ-3 кандидата
                    examples = candidate_info["examples"]
                    if examples:
                        sample_val = examples[0]
                        # Проверяем, не похоже ли это на поле людей по содержимому
                        if isinstance(sample_val, list):
                            # Если в списке есть элементы, похожие на пользователей
                            if sample_val and any(
                                isinstance(item, (str, dict)) and
                                (isinstance(item, dict) and any(k in item for k in ["name", "id", "email", "label"])) or
                                (isinstance(item, str) and len(item) == 36 and item.count('-') == 4)  # UUID
                                for item in sample_val
                            ):
                                people_prop_id = candidate_id
                                print(f"[Yonote] Выбрано потенциальное поле 'люди' по содержимому: {candidate_id}")
                                break
                        elif isinstance(sample_val, str) and ("," in sample_val or "@" in sample_val):
                            people_prop_id = candidate_id
                            print(f"[Yonote] Выбрано потенциальное поле 'люди' по строковому содержимому: {candidate_id}")
                            break

        for item in items:
            if not isinstance(item, dict):
                continue

            deadline_id = str(item.get("id") or "")
            if not deadline_id:
                continue

            title = str(item.get("title") or "").strip()
            if not title:
                title = "(без названия)"

            description = item.get("description")
            if description is not None:
                description = str(description)

            # Получаем values один раз для всех операций
            values = item.get("values") or {}
            
            # Пытаемся найти дату в разных полях (для календарных событий)
            due_date_raw = (
                item.get("due_date")
                or item.get("dueDate")
                or item.get("date")
                or item.get("startDate")
                or item.get("start_date")
            )
            
            # Если не нашли в корневых полях, ищем в values (для календарных событий)
            if not due_date_raw and isinstance(values, dict):
                # Сначала пробуем использовать date_prop_id, если определили
                if date_prop_id and date_prop_id in values:
                    due_date_raw = values.get(date_prop_id)
                    print(f"[Yonote] Найдена дата в values[{date_prop_id}]: {due_date_raw}")
                else:
                    # Ищем поле типа "date" или "datetime" в values
                    # Проверяем все значения в values
                    for key, val in values.items():
                        if val is None:
                            continue
                            
                        # Timestamp (число)
                        if isinstance(val, (int, float)) and val > 1000000000:
                            due_date_raw = val
                            print(f"[Yonote] Найдена дата в values[{key}] как timestamp: {val}")
                            break
                        
                        # ISO строка
                        elif isinstance(val, str):
                            if "T" in val or ("-" in val and len(val) > 8):
                                due_date_raw = val
                                print(f"[Yonote] Найдена дата в values[{key}] как строка: {val}")
                                break
                        
                        # Структурированный объект
                        elif isinstance(val, dict):
                            # Проверяем различные поля в объекте
                            for date_key in ["start", "date", "value", "end", "from", "to"]:
                                if date_key in val:
                                    due_date_raw = val.get(date_key)
                                    if due_date_raw:
                                        print(f"[Yonote] Найдена дата в values[{key}][{date_key}]: {due_date_raw}")
                                        break
                            if due_date_raw:
                                break
                        
                        # Массив с датами (берем первый элемент)
                        elif isinstance(val, list) and val:
                            first = val[0]
                            if isinstance(first, (int, float)) and first > 1000000000:
                                due_date_raw = first
                                print(f"[Yonote] Найдена дата в values[{key}][0] как timestamp: {first}")
                                break
                            elif isinstance(first, dict):
                                for date_key in ["start", "date", "value"]:
                                    if date_key in first:
                                        due_date_raw = first.get(date_key)
                                        if due_date_raw:
                                            print(f"[Yonote] Найдена дата в values[{key}][0][{date_key}]: {due_date_raw}")
                                            break
                                if due_date_raw:
                                    break
            
            # Парсим дату
            due_date = self._parse_datetime(due_date_raw)
            if due_date:
                print(f"[Yonote] + Извлечена дата для '{title}': {due_date}")
            else:
                # Логируем структуру values для отладки (только ключи, чтобы не засорять логи)
                if isinstance(values, dict) and values:
                    keys = list(values.keys())[:5]  # Первые 5 ключей
                    print(f"[Yonote] ! Не удалось извлечь дату для '{title}', доступные keys в values: {keys}")
                else:
                    print(f"[Yonote] ! Не удалось извлечь дату для '{title}', raw: {due_date_raw}, values пуст")

            user_identifier = item.get("user") or item.get("owner") or item.get("email")

            # Извлекаем всех людей из поля «люди» в values
            current_values = item.get("values") or {}
            if isinstance(current_values, dict) and people_prop_id and people_prop_id in current_values:
                people_value = current_values.get(people_prop_id)
                if isinstance(people_value, list) and people_value:
                    # Извлекаем ID пользователей из списка
                    user_ids = [user_id for user_id in people_value if isinstance(user_id, str)]
                    if user_ids:
                        # Теперь нужно получить имена пользователей по ID
                        # Ищем информацию о пользователях в createdBy, updatedBy и других местах
                        user_names = []

                        # Словарь с информацией о пользователях из разных источников
                        user_info = {}

                        # Добавляем информацию из createdBy
                        created_by = item.get("createdBy")
                        if created_by and isinstance(created_by, dict) and "id" in created_by:
                            user_info[created_by["id"]] = created_by.get("name") or created_by.get("email") or created_by.get("username", "Unknown")

                        # Добавляем информацию из updatedBy
                        updated_by = item.get("updatedBy")
                        if updated_by and isinstance(updated_by, dict) and "id" in updated_by:
                            user_info[updated_by["id"]] = updated_by.get("name") or updated_by.get("email") or updated_by.get("username", "Unknown")

                        # Если есть collaboratorIds, добавляем информацию о них
                        collaborator_ids = item.get("collaboratorIds", [])
                        if isinstance(collaborator_ids, list):
                            # Ищем информацию о каждом участнике в createdBy, updatedBy или в других местах
                            for user_id in user_ids:
                                if user_id in user_info:
                                    user_names.append(user_info[user_id])
                                else:
                                    # Если не нашли информацию в уже известных источниках,
                                    # возможно, нужно искать в других местах ответа API
                                    # Временно используем ID как fallback
                                    user_names.append(user_id)

                        if user_names:
                            user_identifier = ", ".join(user_names)
                            if len(user_names) > 1:
                                print(f"[Yonote] Извлечено {len(user_names)} людей из поля 'люди' ({people_prop_id}): {user_identifier}")
                            else:
                                print(f"[Yonote] Извлечён user_identifier из поля 'люди' ({people_prop_id}): {user_identifier}")
            elif isinstance(current_values, dict) and not people_prop_id:
                # Если не определили поле "люди" заранее, пробуем найти его в этом элементе
                # Основываясь на нашем анализе, ищем поле, которое содержит список пользователей
                for key, val in current_values.items():
                    # Вариант 1: Похоже на структуру поля «люди» - содержит массив ID пользователей
                    if isinstance(val, list) and val and all(isinstance(item, str) for item in val):
                        # Если все элементы списка - строки похожие на UUID, вероятно это поле "люди" с ID пользователей
                        if all(len(item) == 36 and item.count('-') == 4 for item in val if isinstance(item, str)):
                            people_value = val
                            user_ids = [user_id for user_id in people_value if isinstance(user_id, str)]
                            if user_ids:
                                # Теперь нужно получить имена пользователей по ID
                                user_names = []

                                # Словарь с информацией о пользователях из разных источников
                                user_info = {}

                                # Добавляем информацию из createdBy
                                created_by = item.get("createdBy")
                                if created_by and isinstance(created_by, dict) and "id" in created_by:
                                    user_info[created_by["id"]] = created_by.get("name") or created_by.get("email") or created_by.get("username", "Unknown")

                                # Добавляем информацию из updatedBy
                                updated_by = item.get("updatedBy")
                                if updated_by and isinstance(updated_by, dict) and "id" in updated_by:
                                    user_info[updated_by["id"]] = updated_by.get("name") or updated_by.get("email") or updated_by.get("username", "Unknown")

                                # Ищем имена пользователей по ID
                                for user_id in user_ids:
                                    if user_id in user_info:
                                        user_names.append(user_info[user_id])
                                    else:
                                        # Если не нашли имя пользователя по ID, используем ID как fallback
                                        # или ищем в других местах
                                        user_names.append(user_id)

                                if user_names:
                                    user_identifier = ", ".join(user_names)
                                    print(f"[Yonote] Найдено поле 'люди' в values[{key}] (через UUID), извлечено: {user_identifier}")
                                    break
                        else:
                            # Вариант 2: Это может быть поле с именами пользователей напрямую (не UUID)
                            # Проверим, может быть, это список имен
                            possible_names = [item for item in val if isinstance(item, str) and len(item) > 0 and len(item) != 36]
                            if possible_names:
                                # Добавляем все возможные имена, кроме UUID
                                direct_names = [name for name in possible_names if not (len(name) == 36 and name.count('-') == 4)]
                                if direct_names:
                                    user_identifier = ", ".join(direct_names)
                                    print(f"[Yonote] Найдено поле 'люди' в values[{key}] (с именами напрямую), извлечено: {user_identifier}")
                                    break
                    # Вариант 3: Поле может содержать строку с именами пользователей
                    elif isinstance(val, str) and ("," in val or "@" in val):
                        # Это может быть строка с именами пользователей
                        user_identifier = val
                        print(f"[Yonote] Найдено поле 'люди' в values[{key}] (как строка), извлечено: {user_identifier}")
                        break

            # Если не нашли людей в основном поле, пробуем использовать информацию из createdBy/updatedBy
            if user_identifier is None or user_identifier == "":
                # Проверяем информацию из createdBy
                created_by = item.get("createdBy")
                if created_by and isinstance(created_by, dict):
                    created_by_name = created_by.get("name") or created_by.get("email") or created_by.get("username")
                    if created_by_name:
                        user_identifier = created_by_name
                        print(f"[Yonote] Используем информацию из createdBy: {user_identifier}")

                # Если всё ещё нет идентификатора, пробуем updatedBy
                if user_identifier is None or user_identifier == "":
                    updated_by = item.get("updatedBy")
                    if updated_by and isinstance(updated_by, dict):
                        updated_by_name = updated_by.get("name") or updated_by.get("email") or updated_by.get("username")
                        if updated_by_name:
                            user_identifier = updated_by_name
                            print(f"[Yonote] Используем информацию из updatedBy: {user_identifier}")

            if user_identifier is not None:
                user_identifier = str(user_identifier)

            deadline = YonoteDeadline(
                id=deadline_id,
                title=title,
                description=description,
                due_date=due_date,
                user_identifier=user_identifier,
            )
            results.append(deadline)
            
            # Логируем для отладки
            print(f"[Yonote] Обработан дедлайн: '{title}', дата: {due_date}, люди: {user_identifier}")

        print(f"[Yonote] Всего обработано дедлайнов: {len(results)}")
        return results

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
                print(f"[Yonote] Дедлайн '{d.title}' соответствует пользователю '{target}'")

        print(f"[Yonote] Отфильтровано {len(result)} дедлайнов из {len(list(deadlines))} для пользователя '{target}'")
        return result

    async def fetch_deadlines_raw(self) -> List[YonoteDeadline]:
        """
        Получить дедлайны через CSV экспорт API.
        """
        if not self.api_key or not self.calendar_id:
            raise YonoteAuthError("YONOTE_API_KEY и/или YONOTE_CALENDAR_ID не заданы")

        csv_url = "https://app.yonote.ru/api/database.export_csv"

        params = {
            "databaseId": self.calendar_id,
            "token": self.api_key
        }

        print(f"[Yonote CSV] Запрос CSV по адресу: {csv_url}")
        print(f"[Yonote CSV] Параметры: {params}")

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(csv_url, params=params) as resp:
                    print(f"[Yonote CSV] Статус ответа: {resp.status}")
                    if resp.status == 200:
                        csv_content = await resp.text()
                        print(f"[Yonote CSV] Получено {len(csv_content)} символов CSV")

                        # Обрабатываем CSV контент
                        return self.parse_csv_to_deadlines(csv_content)
                    else:
                        text = await resp.text()
                        print(f"[Yonote CSV] Ошибка {resp.status}: {text}")
                        raise YonoteClientError(f"Ошибка при получении CSV: {resp.status} - {text}")
            except Exception as e:
                print(f"[Yonote CSV] Исключение при запросе: {e}")
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
            print("[Yonote CSV] Пустой CSV файл")
            return []

        # Возвращаемся к началу и читаем как CSV
        csv_io.seek(0)
        reader = csv.reader(csv_io, delimiter=';', quotechar='"')

        # Чтение заголовков
        headers = next(reader, None)
        if not headers:
            print("[Yonote CSV] Нет заголовков в CSV")
            return []

        print(f"[Yonote CSV] Найдены заголовки: {headers}")

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
            print(f"[Yonote CSV] Не найден столбец с названиями: {headers}")
            return []

        # Проверяем, что дедлайны есть
        deadlines = []
        for row_num, row in enumerate(reader, start=2):  # начинаем с 2, т.к. 1 - заголовки
            if len(row) <= title_idx:
                print(f"[Yonote CSV] Строка {row_num} слишком короткая, пропуск")
                continue

            title = row[title_idx].strip() if title_idx < len(row) else ""
            if not title or title in ["", ";", ";;", ";;;"]:  # Пустая строка или заголовки
                continue

            # Получаем остальные поля
            people = row[people_idx].strip() if people_idx is not None and people_idx < len(row) else None
            song_desc = row[song_idx].strip() if song_idx is not None and song_idx < len(row) else None
            date_str = row[date_idx].strip() if date_idx is not None and date_idx < len(row) else None

            # Парсим дату
            due_date = self._parse_datetime(date_str) if date_str else None

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
            print(f"[Yonote CSV] Обработан дедлайн #{len(deadlines)}: '{title}', люди: {people}, дата: {due_date}")

        print(f"[Yonote CSV] Всего обработано {len(deadlines)} дедлайнов из CSV")
        return deadlines

    def parse_deadlines(self, raw: Any) -> List[YonoteDeadline]:
        """
        Парсит ответ Yonote в список YonoteDeadline.

        Для CSV API этот метод не нужен, но оставляем для совместимости.
        """
        # Данный метод будет вызван, но если raw - это список из CSV, возвращаем его
        if isinstance(raw, list):
            return raw
        return []


async def fetch_user_deadlines(user_identifier: str | None = None) -> List[YonoteDeadline]:
    """
    Вспомогательная высокоуровневая функция:
    - делает запрос к Yonote через CSV экспорт API
    - парсит дедлайны
    - фильтрует по пользователю (если указан)
    """
    client = YonoteClient()
    raw = await client.fetch_deadlines_raw()  # CSV API не принимает user в параметрах
    # Если нужна фильтрация по пользователю - делаем её отдельно
    if user_identifier:
        return client.filter_deadlines_by_user(raw, user_identifier=user_identifier)
    else:
        return raw


if __name__ == "__main__":
    # Простой ручной тест (будет работать, если заданы YONOTE_API_KEY и YONOTE_BASE_URL)
    async def _test() -> None:
        try:
            deadlines = await fetch_user_deadlines(None)
            print(f"Получено дедлайнов из Yonote: {len(deadlines)}")
            for d in deadlines[:5]:
                print(d)
        except Exception as e:  # noqa: BLE001
            print("Ошибка при запросе к Yonote:", e)

    asyncio.run(_test())



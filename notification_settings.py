"""
Модуль для управления персональными настройками уведомлений пользователей.
"""

import json
import logging
from datetime import datetime, time
from typing import Optional

from db import SessionLocal
from models import UserNotificationSettings

logger = logging.getLogger(__name__)

# Значения по умолчанию
DEFAULT_SETTINGS = {
    "notifications_enabled": True,
    "notification_hour": 9,
    "daily_reminders": True,
    "weekly_reminders": True,
    "halfway_reminders": True,
    "weekly_days": [1, 2, 3, 4, 5],  # Понедельник-Пятница
    "days_before_warning": 1,
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "08:00",
}

# Словарь дней недели для парсинга
WEEKDAY_NAMES = {
    'пн': 0, 'понедельник': 0, 'monday': 0,
    'вт': 1, 'вторник': 1, 'tuesday': 1,
    'ср': 2, 'среда': 2, 'wednesday': 2,
    'чт': 3, 'четверг': 3, 'thursday': 3,
    'пт': 4, 'пятница': 4, 'friday': 4,
    'сб': 5, 'суббота': 5, 'saturday': 5,
    'вс': 6, 'воскресенье': 6, 'sunday': 6,
}


def get_user_notification_settings(user_id: int) -> Optional[UserNotificationSettings]:
    """
    Получить настройки уведомлений пользователя.

    Args:
        user_id: ID пользователя

    Returns:
        UserNotificationSettings или None если не найдено
    """
    session = SessionLocal()
    try:
        settings = session.query(UserNotificationSettings).filter_by(user_id=user_id).first()
        return settings
    finally:
        session.close()


def create_default_settings(user_id: int) -> UserNotificationSettings:
    """
    Создать настройки по умолчанию для пользователя.

    Args:
        user_id: ID пользователя

    Returns:
        UserNotificationSettings: Созданные настройки
    """
    session = SessionLocal()
    try:
        settings = UserNotificationSettings(
            user_id=user_id,
            notifications_enabled=DEFAULT_SETTINGS["notifications_enabled"],
            notification_hour=DEFAULT_SETTINGS["notification_hour"],
            daily_reminders=DEFAULT_SETTINGS["daily_reminders"],
            weekly_reminders=DEFAULT_SETTINGS["weekly_reminders"],
            halfway_reminders=DEFAULT_SETTINGS["halfway_reminders"],
            weekly_days=json.dumps(DEFAULT_SETTINGS["weekly_days"]),
            days_before_warning=DEFAULT_SETTINGS["days_before_warning"],
            quiet_hours_start=DEFAULT_SETTINGS["quiet_hours_start"],
            quiet_hours_end=DEFAULT_SETTINGS["quiet_hours_end"],
        )
        session.add(settings)
        session.commit()
        session.refresh(settings)
        logger.info(f"Созданы настройки уведомлений по умолчанию для пользователя {user_id}")
        return settings
    finally:
        session.close()


def get_or_create_user_settings(user_id: int) -> UserNotificationSettings:
    """
    Получить настройки пользователя или создать по умолчанию.

    Args:
        user_id: ID пользователя

    Returns:
        UserNotificationSettings: Настройки пользователя
    """
    settings = get_user_notification_settings(user_id)
    if not settings:
        settings = create_default_settings(user_id)
    return settings


def should_send_notification_to_user(user_id: int, notification_type: str) -> bool:
    """
    Проверить, нужно ли отправлять уведомление пользователю с учетом его настроек.

    Args:
        user_id: ID пользователя
        notification_type: Тип уведомления ("daily", "weekly", "halfway")

    Returns:
        bool: True если нужно отправить
    """
    try:
        settings = get_or_create_user_settings(user_id)

        # Проверяем, включены ли уведомления вообще
        if not settings.notifications_enabled:
            return False

        # Проверяем тихий режим (quiet hours)
        now = datetime.now()
        current_time = now.time()

        if settings.quiet_hours_start and settings.quiet_hours_end:
            try:
                quiet_start = time.fromisoformat(settings.quiet_hours_start)
                quiet_end = time.fromisoformat(settings.quiet_hours_end)

                # Если тихий режим пересекает полночь (например, 22:00 - 08:00)
                if quiet_start > quiet_end:
                    if current_time >= quiet_start or current_time <= quiet_end:
                        logger.debug(f"Тихий режим для пользователя {user_id}: текущее время {current_time} в интервале {quiet_start}-{quiet_end}")
                        return False
                else:
                    if quiet_start <= current_time <= quiet_end:
                        logger.debug(f"Тихий режим для пользователя {user_id}: текущее время {current_time} в интервале {quiet_start}-{quiet_end}")
                        return False
            except ValueError as e:
                logger.warning(f"Ошибка парсинга quiet hours для пользователя {user_id}: {e}")

        # Проверяем тип уведомления
        if notification_type == "daily" and not settings.daily_reminders:
            return False
        elif notification_type == "weekly" and not settings.weekly_reminders:
            return False
        elif notification_type == "halfway" and not settings.halfway_reminders:
            return False

        # Для еженедельных уведомлений проверяем день недели
        if notification_type == "weekly":
            try:
                weekly_days = json.loads(settings.weekly_days) if settings.weekly_days else []
                current_weekday = now.weekday()  # 0 = Понедельник, 6 = Воскресенье
                if current_weekday not in weekly_days:
                    return False
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Ошибка парсинга weekly_days для пользователя {user_id}: {e}")
                return False

        return True

    except Exception as e:
        logger.error(f"Ошибка при проверке настроек уведомлений для пользователя {user_id}: {e}")
        return True  # В случае ошибки отправляем уведомление (fail-safe)


def update_user_notification_settings(user_id: int, **kwargs) -> bool:
    """
    Обновить настройки уведомлений пользователя.

    Args:
        user_id: ID пользователя
        **kwargs: Настройки для обновления

    Returns:
        bool: True если успешно обновлено
    """
    session = SessionLocal()
    try:
        settings = session.query(UserNotificationSettings).filter_by(user_id=user_id).first()

        if not settings:
            settings = create_default_settings(user_id)
            session.add(settings)
            session.commit()
            session.refresh(settings)

        # Обновляем настройки
        updated = False
        for key, value in kwargs.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
                updated = True
                logger.debug(f"Обновлена настройка {key}={value} для пользователя {user_id}")

        if updated:
            settings.updated_at = datetime.now()
            session.commit()
            logger.info(f"Обновлены настройки уведомлений для пользователя {user_id}")
            return True
        else:
            logger.warning(f"Не найдено настроек для обновления пользователя {user_id}")
            return False

    except Exception as e:
        logger.error(f"Ошибка при обновлении настроек уведомлений для пользователя {user_id}: {e}")
        return False
    finally:
        session.close()


def update_user_setting(user_id: int, setting_name: str, value) -> bool:
    """
    Обновить настройку пользователя.

    Args:
        user_id: ID пользователя
        setting_name: Название настройки
        value: Новое значение

    Returns:
        bool: True если успешно обновлено
    """
    session = SessionLocal()
    try:
        settings = session.query(UserNotificationSettings).filter_by(user_id=user_id).first()

        if not settings:
            settings = create_default_settings(user_id)
            session.add(settings)
            session.commit()
            session.refresh(settings)

        # Обновляем настройку
        if hasattr(settings, setting_name):
            setattr(settings, setting_name, value)
            settings.updated_at = datetime.now()
            session.commit()
            logger.info(f"Обновлена настройка {setting_name}={value} для пользователя {user_id}")
            return True
        else:
            logger.warning(f"Неизвестная настройка {setting_name} для пользователя {user_id}")
            return False

    except Exception as e:
        logger.error(f"Ошибка при обновлении настройки {setting_name} для пользователя {user_id}: {e}")
        return False
    finally:
        session.close()


def parse_weekly_days(text: str) -> list[int]:
    """
    Парсить дни недели из текста.

    Поддерживаемые форматы:
    - "пн, ср, пт"
    - "пн-ср, пт-вс"
    - "1,3,5" (номера дней)

    Args:
        text: Текст с днями недели

    Returns:
        list[int]: Список номеров дней (0=Пн, 6=Вс)
    """
    days = []
    parts = [p.strip() for p in text.lower().replace(' ', '').split(',')]

    for part in parts:
        if '-' in part:
            # Диапазон: "пн-ср"
            start_end = part.split('-')
            if len(start_end) == 2:
                start_name = start_end[0].strip()
                end_name = start_end[1].strip()

                start_day = WEEKDAY_NAMES.get(start_name)
                end_day = WEEKDAY_NAMES.get(end_name)

                if start_day is not None and end_day is not None:
                    if start_day <= end_day:
                        days.extend(range(start_day, end_day + 1))
                    else:
                        # Если диапазон пересекает неделю: "пт-вт"
                        days.extend(range(start_day, 7))  # от start до конца недели
                        days.extend(range(0, end_day + 1))  # от начала недели до end
        else:
            # Одиночный день
            day = WEEKDAY_NAMES.get(part.strip())
            if day is not None:
                days.append(day)
            else:
                # Попробовать парсить как число
                try:
                    day_num = int(part.strip())
                    if 0 <= day_num <= 6:
                        days.append(day_num)
                except ValueError:
                    pass

    # Убираем дубликаты и сортируем
    return sorted(list(set(days)))


def reset_user_notification_settings(user_id: int) -> bool:
    """
    Сбросить настройки уведомлений пользователя к значениям по умолчанию.

    Args:
        user_id: ID пользователя

    Returns:
        bool: True если успешно сброшено
    """
    session = SessionLocal()
    try:
        settings = session.query(UserNotificationSettings).filter_by(user_id=user_id).first()

        if settings:
            # Обновляем все настройки к значениям по умолчанию
            for key, value in DEFAULT_SETTINGS.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)

            settings.updated_at = datetime.now()
            session.commit()
            logger.info(f"Настройки уведомлений сброшены к умолчанию для пользователя {user_id}")
            return True
        else:
            # Если настроек нет, создаем с настройками по умолчанию
            create_default_settings(user_id)
            return True

    except Exception as e:
        logger.error(f"Ошибка при сбросе настроек уведомлений для пользователя {user_id}: {e}")
        return False
    finally:
        session.close()


def format_weekly_days(days: list[int]) -> str:
    """
    Форматировать список дней недели в читаемый текст.

    Args:
        days: Список номеров дней

    Returns:
        str: Отформатированный текст
    """
    if not days:
        return "Нет дней"

    day_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

    # Группируем в диапазоны
    if len(days) == 7:
        return "Ежедневно"

    ranges = []
    start = days[0]
    prev = days[0]

    for day in days[1:]:
        if day == prev + 1:
            prev = day
        else:
            if start == prev:
                ranges.append(day_names[start])
            else:
                ranges.append(f"{day_names[start]}-{day_names[prev]}")
            start = prev = day

    # Добавляем последний диапазон
    if start == prev:
        ranges.append(day_names[start])
    else:
        ranges.append(f"{day_names[start]}-{day_names[prev]}")

    return ", ".join(ranges)


def get_notification_summary(user_id: int) -> str:
    """
    Получить текстовое представление настроек пользователя (для совместимости).

    Args:
        user_id: ID пользователя

    Returns:
        str: Форматированный текст настроек
    """
    return get_user_settings_text(user_id)


def get_user_settings_text(user_id: int) -> str:
    """
    Получить текстовое представление настроек пользователя.

    Args:
        user_id: ID пользователя

    Returns:
        str: Форматированный текст настроек
    """
    settings = get_or_create_user_settings(user_id)

    # Парсим дни недели
    try:
        weekly_days = json.loads(settings.weekly_days) if settings.weekly_days else []
    except json.JSONDecodeError:
        weekly_days = DEFAULT_SETTINGS["weekly_days"]

    lines = [
        "⚙️ *Настройки уведомлений*\n",
        f"🔔 Уведомления: {'ВКЛ' if settings.notifications_enabled else 'ВЫКЛ'}",
        f"⏰ Время отправки: {settings.notification_hour:02d}:00",
        "",
        f"📅 Ежедневные напоминания: {'ВКЛ' if settings.daily_reminders else 'ВЫКЛ'}",
        f"📆 Еженедельные напоминания: {'ВКЛ' if settings.weekly_reminders else 'ВЫКЛ'}",
        f"⏳ Напоминания за половину срока: {'ВКЛ' if settings.halfway_reminders else 'ВЫКЛ'}",
        "",
        f"⚠️ Предупреждать за: {settings.days_before_warning} дн.",
        f"📊 Дни недели: {format_weekly_days(weekly_days)}",
        "",
        f"🌙 Тихий режим: {settings.quiet_hours_start}-{settings.quiet_hours_end}",
    ]

    return "\n".join(lines)
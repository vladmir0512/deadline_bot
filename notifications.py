"""
Модуль для отправки уведомлений о приближающихся дедлайнах.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from aiogram import Bot

from db import SessionLocal
from models import Deadline, DeadlineStatus, Subscription
from services import format_deadline, get_user_deadlines

logger = logging.getLogger(__name__)

# Время для фильтрации дедлайнов
NOTIFICATION_WINDOWS = {
    "today": timedelta(days=0),  # Сегодня
    "tomorrow": timedelta(days=1),  # Завтра
    "week": timedelta(days=7),  # В течение недели
}


def get_deadlines_in_window(
    deadlines: list[Deadline],
    window_days: int = 1,
) -> list[Deadline]:
    """
    Получить дедлайны, которые наступают в указанном окне времени.

    Args:
        deadlines: Список дедлайнов
        window_days: Количество дней вперёд для проверки

    Returns:
        Список дедлайнов в окне
    """
    now = datetime.now(UTC)
    window_end = now + timedelta(days=window_days)

    result = []
    for deadline in deadlines:
        if not deadline.due_date:
            continue

        # Проверяем, что дедлайн в будущем и в пределах окна
        if now <= deadline.due_date <= window_end:
            result.append(deadline)

    return result


def get_deadlines_today(deadlines: list[Deadline]) -> list[Deadline]:
    """Получить дедлайны на сегодня."""
    return get_deadlines_in_window(deadlines, window_days=0)


def get_deadlines_tomorrow(deadlines: list[Deadline]) -> list[Deadline]:
    """Получить дедлайны на завтра."""
    now = datetime.now(UTC)
    tomorrow_start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_end = tomorrow_start + timedelta(days=1)

    result = []
    for deadline in deadlines:
        if not deadline.due_date:
            continue
        if tomorrow_start <= deadline.due_date < tomorrow_end:
            result.append(deadline)

    return result


def get_deadlines_this_week(deadlines: list[Deadline]) -> list[Deadline]:
    """Получить дедлайны в течение недели."""
    return get_deadlines_in_window(deadlines, window_days=7)


def should_send_notification(deadline: Deadline, notification_type: str) -> bool:
    """
    Проверить, нужно ли отправлять уведомление (предотвращение дублирования).

    Args:
        deadline: Дедлайн
        notification_type: Тип уведомления ("approaching", "today", "tomorrow")

    Returns:
        True если нужно отправить, False если уже отправляли недавно
    """
    if not deadline.last_notified_at:
        return True

    now = datetime.now(UTC)
    last_notified = deadline.last_notified_at

    # Для дедлайнов на сегодня - отправляем не чаще раза в час
    if notification_type == "today":
        return (now - last_notified).total_seconds() >= 3600

    # Для дедлайнов на завтра - отправляем не чаще раза в 6 часов
    if notification_type == "tomorrow":
        return (now - last_notified).total_seconds() >= 21600

    # Для остальных - отправляем не чаще раза в день
    return (now - last_notified).days >= 1


async def send_deadline_notification(
    bot: Bot,
    telegram_id: int,
    deadline: Deadline,
    notification_type: str = "approaching",
) -> bool:
    """
    Отправить уведомление о дедлайне пользователю.

    Args:
        bot: Экземпляр бота
        telegram_id: Telegram ID пользователя
        deadline: Дедлайн
        notification_type: Тип уведомления ("approaching", "today", "tomorrow")

    Returns:
        True если отправлено успешно, False в противном случае
    """
    # Проверяем, нужно ли отправлять уведомление
    if not should_send_notification(deadline, notification_type):
        logger.debug(
            f"Пропуск уведомления для дедлайна {deadline.id}: "
            f"уже отправляли {deadline.last_notified_at}"
        )
        return False

    try:
        # Формируем сообщение
        emoji_map = {
            "approaching": "⏰",
            "today": "🔴",
            "tomorrow": "🟡",
        }
        emoji = emoji_map.get(notification_type, "⏰")

        if notification_type == "today":
            header = f"{emoji} *Дедлайн сегодня!*"
        elif notification_type == "tomorrow":
            header = f"{emoji} *Дедлайн завтра*"
        else:
            header = f"{emoji} *Приближается дедлайн*"

        message_text = f"{header}\n\n{format_deadline(deadline)}"

        await bot.send_message(chat_id=telegram_id, text=message_text, parse_mode="Markdown")

        # Обновляем время последнего уведомления
        session = SessionLocal()
        try:
            deadline.last_notified_at = datetime.now(UTC)
            session.add(deadline)
            session.commit()
        finally:
            session.close()

        logger.info(f"Уведомление отправлено пользователю {telegram_id} о дедлайне {deadline.id}")
        return True

    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления пользователю {telegram_id}: {e}", exc_info=True)
        return False


async def check_and_notify_deadlines(bot: Bot) -> dict[str, int]:
    """
    Проверить дедлайны и отправить уведомления активным подписчикам.

    Args:
        bot: Экземпляр бота

    Returns:
        Словарь со статистикой: {"users_notified": ..., "notifications_sent": ...}
    """
    session = SessionLocal()
    users_notified = 0
    notifications_sent = 0

    try:
        # Получаем всех пользователей с активными подписками
        active_subscriptions = (
            session.query(Subscription)
            .filter_by(notification_type="telegram", active=True)
            .all()
        )

        for subscription in active_subscriptions:
            user = subscription.user
            if not user:
                continue

            # Получаем активные дедлайны пользователя
            deadlines = get_user_deadlines(user.id, status=DeadlineStatus.ACTIVE)

            if not deadlines:
                continue

            # Проверяем дедлайны на сегодня
            today_deadlines = get_deadlines_today(deadlines)
            for deadline in today_deadlines:
                if await send_deadline_notification(bot, user.telegram_id, deadline, "today"):
                    notifications_sent += 1

            # Проверяем дедлайны на завтра (только если нет дедлайнов на сегодня)
            if not today_deadlines:
                tomorrow_deadlines = get_deadlines_tomorrow(deadlines)
                for deadline in tomorrow_deadlines:
                    if await send_deadline_notification(bot, user.telegram_id, deadline, "tomorrow"):
                        notifications_sent += 1

            # Проверяем дедлайны в течение недели (только если нет дедлайнов на сегодня/завтра)
            if not today_deadlines and not tomorrow_deadlines:
                week_deadlines = get_deadlines_this_week(deadlines)
                # Отправляем только ближайший дедлайн в неделе
                if week_deadlines:
                    nearest = min(week_deadlines, key=lambda d: d.due_date or datetime.max.replace(tzinfo=UTC))
                    if await send_deadline_notification(bot, user.telegram_id, nearest, "approaching"):
                        notifications_sent += 1

            if notifications_sent > 0:
                users_notified += 1

        logger.info(
            f"Проверка уведомлений завершена: "
            f"пользователей уведомлено {users_notified}, отправлено уведомлений {notifications_sent}"
        )

        return {
            "users_notified": users_notified,
            "notifications_sent": notifications_sent,
        }

    except Exception as e:
        logger.error(f"Ошибка при проверке уведомлений: {e}", exc_info=True)
        return {"users_notified": 0, "notifications_sent": 0}
    finally:
        session.close()


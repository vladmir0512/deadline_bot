"""
Модуль для отправки уведомлений о приближающихся дедлайнах.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta, timezone

from aiogram import Bot

from db import SessionLocal
from models import Deadline, DeadlineStatus, Subscription
from services import format_deadline, get_user_deadlines
from notification_settings import get_or_create_user_settings

logger = logging.getLogger(__name__)

# Настройка часового пояса (GMT+3, Moscow)
MOSCOW_TZ = timezone(timedelta(hours=3))

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

        # Убеждаемся, что дата дедлайна имеет timezone
        due_date = deadline.due_date
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=UTC)

        # Проверяем, что дедлайн в будущем и в пределах окна
        if now <= due_date <= window_end:
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

        # Убеждаемся, что дата дедлайна имеет timezone
        due_date = deadline.due_date
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=UTC)

        if tomorrow_start <= due_date < tomorrow_end:
            result.append(deadline)

    return result


def get_deadlines_this_week(deadlines: list[Deadline]) -> list[Deadline]:
    """Получить дедлайны в течение недели."""
    return get_deadlines_in_window(deadlines, window_days=7)


def get_deadlines_at_halfway(deadlines: list[Deadline]) -> list[Deadline]:
    """
    Получить дедлайны, для которых наступила половина срока или уже прошла, но уведомление не было отправлено.

    Половина срока = середина между created_at и due_date.
    """
    now = datetime.now(UTC)
    result = []

    for deadline in deadlines:
        if not deadline.due_date or not deadline.created_at:
            continue

        # Убеждаемся, что даты имеют timezone
        due_date = deadline.due_date
        created_at = deadline.created_at

        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=UTC)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        # Проверяем, что дедлайн еще не прошел
        if due_date <= now:
            continue

        # Вычисляем половину срока
        total_duration = due_date - created_at
        halfway_point = created_at + (total_duration / 2)

        # Проверяем, наступила ли половина срока
        time_diff = (now - halfway_point).total_seconds()

        # Окно для отправки уведомления:
        # 1. От 30 минут до половины до 3 часов после половины (основное окно)
        # 2. ИЛИ дедлайн уже прошел половину срока И уведомление никогда не отправлялось
        in_main_window = -1800 <= time_diff <= 10800  # От 30 минут до половины до 3 часов после
        past_halfway_no_notification = time_diff > 0 and not deadline.last_notified_at

        if in_main_window or past_halfway_no_notification:
            result.append(deadline)
            # Конвертируем времена в Moscow timezone для логирования
            created_moscow = created_at.astimezone(MOSCOW_TZ)
            due_moscow = due_date.astimezone(MOSCOW_TZ)
            halfway_moscow = halfway_point.astimezone(MOSCOW_TZ)
            now_moscow = now.astimezone(MOSCOW_TZ)

            # Определяем метод расчета для логирования
            total_hours = total_duration.total_seconds() / 3600
            calculation_method = "от времени создания" if total_hours <= 720 else "от текущего времени"

            logger.info(
                f"Дедлайн '{deadline.title}' на половине срока: "
                f"создан {created_moscow.strftime('%Y-%m-%d %H:%M MSK')}, "
                f"дедлайн {due_moscow.strftime('%Y-%m-%d %H:%M MSK')}, "
                f"половина {halfway_moscow.strftime('%Y-%m-%d %H:%M MSK')} ({calculation_method}), "
                f"сейчас {now_moscow.strftime('%Y-%m-%d %H:%M MSK')}, "
                f"разница {time_diff/3600:.1f} часов, "
                f"общая длительность {total_duration.days} дней {total_duration.seconds//3600} часов, "
                f"причина: {'основное окно' if in_main_window else 'прошла половина, нет уведомления'}"
            )

    return result


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
    # Приводим last_notified к timezone-aware, чтобы не падать на разнице naive/aware
    last_notified = (
        deadline.last_notified_at
        if deadline.last_notified_at.tzinfo is not None
        else deadline.last_notified_at.replace(tzinfo=UTC)
    )

    # Для дедлайнов на сегодня - отправляем не чаще раза в час
    if notification_type == "today":
        return (now - last_notified).total_seconds() >= 3600

    # Для дедлайнов на завтра - отправляем не чаще раза в 6 часов
    if notification_type == "tomorrow":
        return (now - last_notified).total_seconds() >= 21600

    # Для уведомления о половине срока - отправляем только один раз
    if notification_type == "halfway":
        # Проверяем, не отправляли ли уже уведомление о половине срока
        # Если отправляли менее 24 часов назад, не отправляем снова
        # (чтобы гарантировать, что уведомление отправится хотя бы один раз)
        time_since_last = (now - last_notified).total_seconds()
        should_send = time_since_last >= 86400  # 24 часа
        if not should_send:
            logger.debug(
                f"Пропуск уведомления о половине срока для дедлайна {deadline.id}: "
                f"последнее уведомление было {time_since_last/3600:.1f} часов назад"
            )
        return should_send

    # Для остальных - отправляем не чаще раза в день
    return (now - last_notified).days >= 1


async def send_grouped_notifications(
    bot: Bot,
    telegram_id: int,
    deadlines: list[Deadline],
    notification_type: str,
) -> bool:
    """
    Отправить групповое уведомление о нескольких дедлайнах.

    Args:
        bot: Экземпляр бота
        telegram_id: Telegram ID пользователя
        deadlines: Список дедлайнов
        notification_type: Тип уведомления ("today", "tomorrow" и т.д.)

    Returns:
        True если отправлено, False иначе
    """
    if not deadlines:
        return False

    # Проверяем, нужно ли отправлять (на основе первого дедлайна)
    if not should_send_notification(deadlines[0], notification_type):
        logger.debug(f"Пропуск группового уведомления типа {notification_type} для пользователя {telegram_id}")
        return False

    try:
        # Формируем сообщение
        emoji_map = {
            "today": "🔴",
            "tomorrow": "🟡",
            "halfway": "⏳",
            "approaching": "⏰",
        }
        emoji = emoji_map.get(notification_type, "⏰")

        if notification_type == "today":
            header = f"{emoji} *Дедлайны сегодня* ({len(deadlines)})"
        elif notification_type == "tomorrow":
            header = f"{emoji} *Дедлайны завтра* ({len(deadlines)})"
        else:
            header = f"{emoji} *Приближающиеся дедлайны* ({len(deadlines)})"

        message_lines = [header, ""]
        for deadline in deadlines:
            message_lines.append(format_deadline(deadline))
            message_lines.append("")  # Разделитель

        message_text = "\n".join(message_lines).strip()

        await bot.send_message(chat_id=telegram_id, text=message_text, parse_mode="Markdown")

        # Обновляем last_notified_at для всех дедлайнов в группе
        session = SessionLocal()
        try:
            now = datetime.now(UTC)
            for deadline in deadlines:
                deadline.last_notified_at = now
                session.add(deadline)
            session.commit()
        finally:
            session.close()

        logger.info(f"Групповое уведомление отправлено пользователю {telegram_id}: {len(deadlines)} дедлайнов типа {notification_type}")
        return True

    except Exception as e:
        logger.error(f"Ошибка при отправке группового уведомления пользователю {telegram_id}: {e}", exc_info=True)
        return False


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
            "halfway": "⏳",
        }
        emoji = emoji_map.get(notification_type, "⏰")

        if notification_type == "today":
            header = f"{emoji} *Дедлайн сегодня!*"
        elif notification_type == "tomorrow":
            header = f"{emoji} *Дедлайн завтра*"
        elif notification_type == "halfway":
            header = f"{emoji} *Прошла половина срока до дедлайна*"
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

            # Получаем настройки уведомлений пользователя
            settings = get_or_create_user_settings(user.id)
            
            # Проверяем, включены ли уведомления
            if not settings.notifications_enabled:
                logger.debug(f"Уведомления отключены для пользователя {user.telegram_id}")
                continue

            # Проверяем текущее время в МСК и сравниваем с настройкой пользователя
            now_moscow = datetime.now(MOSCOW_TZ)
            current_hour = now_moscow.hour
            current_minute = now_moscow.minute
            
            # Для срочных уведомлений (сегодня) отправляем в любое время
            # Для остальных - только в установленное время пользователя
            
            # Получаем активные дедлайны пользователя (включая будущие)
            deadlines = get_user_deadlines(user.id, status=DeadlineStatus.ACTIVE, only_future=True)

            if not deadlines:
                continue

            # Проверяем дедлайны на сегодня (высший приоритет) - отправляем в любое время
            today_deadlines = get_deadlines_today(deadlines)
            if today_deadlines:
                if await send_grouped_notifications(bot, user.telegram_id, today_deadlines, "today"):
                    notifications_sent += 1

            # Если есть срочные уведомления, пропускаем остальные проверки
            if today_deadlines:
                if notifications_sent > 0:
                    users_notified += 1
                continue

            # Для остальных уведомлений проверяем время
            # Уведомления отправляются только в установленный час
            # Учитываем, что планировщик может запускаться не точно в 00 минут
            # Поэтому проверяем, что текущий час совпадает с установленным
            # и минуты находятся в разумном окне (0-30 минут часа)
            time_match = (
                current_hour == settings.notification_hour and 
                current_minute < 30  # Окно в первые 30 минут часа
            )
            
            if not time_match:
                logger.debug(
                    f"Пропуск уведомлений для пользователя {user.telegram_id}: "
                    f"текущее время {current_hour:02d}:{current_minute:02d} МСК, "
                    f"установлено {settings.notification_hour:02d}:00 МСК"
                )
                continue

            # Проверяем дедлайны на завтра
            tomorrow_deadlines = get_deadlines_tomorrow(deadlines)
            if tomorrow_deadlines:
                if await send_grouped_notifications(bot, user.telegram_id, tomorrow_deadlines, "tomorrow"):
                    notifications_sent += 1

            # Проверяем дедлайны на половине срока (независимо от других проверок)
            # Это важное уведомление, которое должно отправляться отдельно
            halfway_deadlines = get_deadlines_at_halfway(deadlines)
            logger.debug(
                f"Проверка половины срока для пользователя {user.telegram_id}: "
                f"найдено {len(halfway_deadlines)} дедлайнов на половине срока"
            )
            for deadline in halfway_deadlines:
                if await send_deadline_notification(bot, user.telegram_id, deadline, "halfway"):
                    notifications_sent += 1
                    logger.info(
                        f"✅ Отправлено уведомление о половине срока для дедлайна '{deadline.title}' "
                        f"пользователю {user.telegram_id}"
                    )
                else:
                    logger.debug(
                        f"Пропущено уведомление о половине срока для дедлайна '{deadline.title}' "
                        f"(уже отправляли недавно)"
                    )

            # Проверяем дедлайны в течение недели (только если нет дедлайнов на завтра)
            if not tomorrow_deadlines:
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


async def send_message_to_all_subscribers(
    bot: Bot,
    message_text: str,
    parse_mode: str | None = "Markdown",
) -> dict[str, int]:
    """
    Отправить сообщение всем пользователям с активными подписками.

    Args:
        bot: Экземпляр бота
        message_text: Текст сообщения для отправки
        parse_mode: Режим парсинга (Markdown, HTML или None)

    Returns:
        Словарь со статистикой: {"total_subscribers": ..., "sent": ..., "failed": ...}
    """
    session = SessionLocal()
    sent_count = 0
    failed_count = 0
    total_subscribers = 0

    try:
        # Получаем всех пользователей с активными подписками
        active_subscriptions = (
            session.query(Subscription)
            .filter_by(notification_type="telegram", active=True)
            .all()
        )

        total_subscribers = len(active_subscriptions)
        logger.info(f"Отправка сообщения {total_subscribers} подписанным пользователям")

        for subscription in active_subscriptions:
            user = subscription.user
            if not user:
                continue

            try:
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=message_text,
                    parse_mode=parse_mode,
                )
                sent_count += 1
                logger.debug(f"Сообщение отправлено пользователю {user.telegram_id}")
            except Exception as e:
                failed_count += 1
                logger.error(
                    f"Ошибка при отправке сообщения пользователю {user.telegram_id}: {e}",
                    exc_info=True,
                )

        logger.info(
            f"Рассылка завершена: всего {total_subscribers}, "
            f"отправлено {sent_count}, ошибок {failed_count}"
        )

        return {
            "total_subscribers": total_subscribers,
            "sent": sent_count,
            "failed": failed_count,
        }

    except Exception as e:
        logger.error(f"Ошибка при рассылке сообщений: {e}", exc_info=True)
        return {"total_subscribers": 0, "sent": 0, "failed": 0}
    finally:
        session.close()


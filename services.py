"""
Вспомогательные функции для работы с базой данных.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import or_

from db import SessionLocal
from models import Deadline, DeadlineStatus, Subscription, User


def get_or_create_user(telegram_id: int, username: str | None = None) -> User:
    """
    Получить пользователя по telegram_id или создать нового.

    Args:
        telegram_id: ID пользователя в Telegram
        username: Имя пользователя в Telegram (опционально)

    Returns:
        Объект User
    """
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if user:
            return user

        # Создаём нового пользователя (без автоматического username)
        user = User(telegram_id=telegram_id, username=None)  # Не сохраняем Telegram username автоматически
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    finally:
        session.close()


def get_user_by_telegram_id(telegram_id: int) -> User | None:
    """Получить пользователя по telegram_id."""
    session = SessionLocal()
    try:
        return session.query(User).filter_by(telegram_id=telegram_id).first()
    finally:
        session.close()


def update_user_email(telegram_id: int, email: str) -> User | None:
    """
    Обновить email пользователя.

    Args:
        telegram_id: ID пользователя в Telegram
        email: Email адрес

    Returns:
        Объект User или None, если пользователь не найден
    """
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return None

        user.email = email
        session.commit()
        session.refresh(user)
        return user
    finally:
        session.close()


def get_user_deadlines(user_id: int, status: str | None = None, only_future: bool = True, include_no_date: bool = True) -> list[Deadline]:
    """
    Получить дедлайны пользователя.

    Args:
        user_id: ID пользователя в БД
        status: Фильтр по статусу (опционально)
        only_future: Показывать только будущие дедлайны (по умолчанию True)
        include_no_date: Включать дедлайны без даты (по умолчанию True)

    Returns:
        Список дедлайнов
    """
    session = SessionLocal()
    try:
        # Проверяем, что пользователь имеет зарегистрированный ник (для Yonote)
        from models import User
        user = session.query(User).filter_by(id=user_id).first()
        if not user or not user.username:
            # Пользователь не зарегистрирован с ником, возвращаем пустой список
            return []

        query = session.query(Deadline).filter_by(user_id=user_id)
        if status:
            query = query.filter_by(status=status)

        # Фильтруем прошедшие дедлайны
        if only_future:
            now = datetime.now(UTC)
            if include_no_date:
                # Показываем дедлайны в будущем или без даты (но не прошедшие)
                query = query.filter(
                    (Deadline.due_date.is_(None)) |  # Дедлайны без даты
                    (Deadline.due_date >= now)       # Или с датой в будущем
                )
            else:
                # Только дедлайны с датой в будущем
                query = query.filter(
                    Deadline.due_date.isnot(None),  # Только дедлайны с датой
                    Deadline.due_date >= now        # Дедлайны в будущем или сейчас
                )
        else:
            # Если не только будущие - возвращаем все
            pass

        return query.order_by(Deadline.due_date.asc(), Deadline.created_at.desc()).all()
    finally:
        session.close()


def get_user_subscription(user_id: int, notification_type: str = "telegram") -> Subscription | None:
    """
    Получить подписку пользователя.

    Args:
        user_id: ID пользователя в БД
        notification_type: Тип уведомлений (по умолчанию "telegram")

    Returns:
        Объект Subscription или None
    """
    session = SessionLocal()
    try:
        return (
            session.query(Subscription)
            .filter_by(user_id=user_id, notification_type=notification_type)
            .first()
        )
    finally:
        session.close()


def toggle_subscription(user_id: int, notification_type: str = "telegram") -> Subscription:
    """
    Переключить подписку пользователя (создать, если нет, или изменить статус).

    Args:
        user_id: ID пользователя в БД
        notification_type: Тип уведомлений

    Returns:
        Объект Subscription
    """
    session = SessionLocal()
    try:
        subscription = (
            session.query(Subscription)
            .filter_by(user_id=user_id, notification_type=notification_type)
            .first()
        )

        if subscription:
            subscription.active = not subscription.active
        else:
            subscription = Subscription(
                user_id=user_id,
                notification_type=notification_type,
                active=True,
            )
            session.add(subscription)

        session.commit()
        session.refresh(subscription)
        return subscription
    finally:
        session.close()


def delete_user(user_id: int) -> bool:
    """
    Удалить пользователя и все связанные данные (дедлайны, подписки).

    Args:
        user_id: ID пользователя в БД

    Returns:
        True если пользователь был удален, False если не найден
    """
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return False

        session.delete(user)
        session.commit()
        return True
    finally:
        session.close()


def delete_expired_deadlines() -> int:
    """
    Удалить просроченные и завершенные дедлайны из базы данных.

    Returns:
        Количество удаленных дедлайнов
    """
    session = SessionLocal()
    try:
        from datetime import UTC, datetime
        now = datetime.now(UTC)

        # Находим просроченные активные дедлайны (с датой в прошлом)
        expired_deadlines = (
            session.query(Deadline)
            .filter(
                Deadline.due_date < now,  # просроченные
                Deadline.status == DeadlineStatus.ACTIVE,  # активные
                Deadline.due_date.isnot(None)  # с датой
            )
        )

        # Также находим завершенные или отмененные дедлайны
        completed_deadlines = (
            session.query(Deadline)
            .filter(
                or_(
                    Deadline.status == DeadlineStatus.COMPLETED,  # завершенные
                    Deadline.status == DeadlineStatus.CANCELED   # отмененные
                )
            )
        )

        # Объединяем запросы
        all_to_delete = expired_deadlines.union(completed_deadlines)
        deadlines_to_delete = all_to_delete.all()

        count = len(deadlines_to_delete)

        # Удаляем найденные дедлайны
        for deadline in deadlines_to_delete:
            session.delete(deadline)

        if count > 0:
            session.commit()
            from logging import getLogger
            logger = getLogger(__name__)
            logger.info(f"Удалено {count} просроченных/завершенных дедлайнов")

        return count
    finally:
        session.close()


def format_deadline(deadline: Deadline) -> str:
    """
    Форматировать дедлайн для отображения в Telegram.

    Args:
        deadline: Объект Deadline

    Returns:
        Отформатированная строка
    """
    lines = [f"📅 *{deadline.title}*"]

    if deadline.description:
        lines.append(f"📝 {deadline.description}")

    if deadline.due_date:
        # Форматируем дату в московском времени
        due_date_str = deadline.due_date.strftime("%d.%m.%Y %H:%M")
        lines.append(f"⏰ Дедлайн: {due_date_str}")

    status_emoji = {
        DeadlineStatus.ACTIVE: "🟢",
        DeadlineStatus.COMPLETED: "✅",
        DeadlineStatus.CANCELED: "❌",
    }
    status_text = {
        DeadlineStatus.ACTIVE: "Активен",
        DeadlineStatus.COMPLETED: "Завершён",
        DeadlineStatus.CANCELED: "Отменён",
    }
    emoji = status_emoji.get(deadline.status, "⚪")
    text = status_text.get(deadline.status, deadline.status)
    lines.append(f"{emoji} Статус: {text}")

    if deadline.source:
        lines.append(f"🔗 Источник: {deadline.source}")

    return "\n".join(lines)


"""
Вспомогательные функции для работы с базой данных.
"""

from __future__ import annotations

from datetime import UTC, datetime, timezone, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from db import SessionLocal
from models import Deadline, DeadlineStatus, DeadlineVerification, Subscription, User

# Настройка часового пояса (GMT+3, Moscow)
MOSCOW_TZ = timezone(timedelta(hours=3))


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
        if deadline.due_date.tzinfo is None:
            # Если naive datetime, предполагаем UTC
            due_date_moscow = deadline.due_date.replace(tzinfo=UTC).astimezone(MOSCOW_TZ)
        else:
            due_date_moscow = deadline.due_date.astimezone(MOSCOW_TZ)

        due_date_str = due_date_moscow.strftime("%d.%m.%Y %H:%M")
        lines.append(f"⏰ Дедлайн: {due_date_str} (MSK)")

    status_emoji = {
        DeadlineStatus.ACTIVE: "🟢",
        DeadlineStatus.COMPLETED: "✅",
        DeadlineStatus.CANCELED: "❌",
        DeadlineStatus.PENDING_VERIFICATION: "⏳",
    }
    status_text = {
        DeadlineStatus.ACTIVE: "Активен",
        DeadlineStatus.COMPLETED: "Завершён",
        DeadlineStatus.CANCELED: "Отменён",
        DeadlineStatus.PENDING_VERIFICATION: "На проверке",
    }
    emoji = status_emoji.get(deadline.status, "⚪")
    text = status_text.get(deadline.status, deadline.status)
    lines.append(f"{emoji} Статус: {text}")

    if deadline.source:
        lines.append(f"🔗 Источник: {deadline.source}")

    return "\n".join(lines)


def get_all_subscribed_users(notification_type: str = "telegram") -> list[tuple[User, Subscription]]:
    """
    Получить список всех пользователей с активными подписками.

    Args:
        notification_type: Тип уведомлений (по умолчанию "telegram")

    Returns:
        Список кортежей (User, Subscription) для всех подписанных пользователей
    """
    session = SessionLocal()
    try:
        subscriptions = (
            session.query(Subscription)
            .filter_by(notification_type=notification_type, active=True)
            .join(User)
            .order_by(User.created_at.asc())
            .all()
        )

        result = []
        for subscription in subscriptions:
            if subscription.user:
                result.append((subscription.user, subscription))

        return result
    finally:
        session.close()


def request_deadline_verification(deadline_id: int, user_id: int, comment: str | None = None) -> DeadlineVerification | None:
    """
    Создать запрос на проверку выполнения дедлайна.

    Args:
        deadline_id: ID дедлайна
        user_id: ID пользователя
        comment: Комментарий пользователя (опционально)

    Returns:
        Объект DeadlineVerification или None, если дедлайн не найден или уже на проверке
    """
    session = SessionLocal()
    try:
        deadline = session.query(Deadline).filter_by(id=deadline_id, user_id=user_id).first()
        if not deadline:
            return None

        # Проверяем, что дедлайн активен и не на проверке
        if deadline.status != DeadlineStatus.ACTIVE:
            return None

        # Проверяем, нет ли уже активного запроса на проверку
        existing = (
            session.query(DeadlineVerification)
            .filter_by(deadline_id=deadline_id, status="pending")
            .first()
        )
        if existing:
            return None

        # Создаем запрос на проверку
        verification = DeadlineVerification(
            deadline_id=deadline_id,
            user_id=user_id,
            status="pending",
            user_comment=comment,
        )
        session.add(verification)

        # Меняем статус дедлайна на "на проверке"
        deadline.status = DeadlineStatus.PENDING_VERIFICATION
        deadline.updated_at = datetime.now(UTC)

        session.commit()
        session.refresh(verification)
        return verification
    except Exception as e:
        session.rollback()
        from logging import getLogger
        logger = getLogger(__name__)
        logger.error(f"Ошибка при создании запроса на проверку: {e}", exc_info=True)
        return None
    finally:
        session.close()


def get_pending_verifications() -> list[DeadlineVerification]:
    """
    Получить все запросы на проверку, ожидающие решения.

    Returns:
        Список DeadlineVerification со статусом "pending" с загруженными связанными объектами
    """
    session = SessionLocal()
    try:
        # Используем eager loading для загрузки связанных объектов deadline и user
        verifications = (
            session.query(DeadlineVerification)
            .options(
                joinedload(DeadlineVerification.deadline),
                joinedload(DeadlineVerification.user)
            )
            .filter_by(status="pending")
            .order_by(DeadlineVerification.created_at.asc())
            .all()
        )
        # Отсоединяем объекты от сессии, чтобы они были доступны после закрытия сессии
        # Сначала загружаем все связанные объекты, затем отсоединяем
        result = []
        for verification in verifications:
            # Принудительно загружаем связанные объекты
            _ = verification.deadline
            _ = verification.user
            # Отсоединяем объект от сессии
            session.expunge(verification)
            if verification.deadline:
                session.expunge(verification.deadline)
            if verification.user:
                session.expunge(verification.user)
            result.append(verification)
        return result
    finally:
        session.close()


def approve_deadline_verification(verification_id: int, admin_telegram_id: int, comment: str | None = None) -> bool:
    """
    Одобрить выполнение дедлайна.

    Args:
        verification_id: ID запроса на проверку
        admin_telegram_id: Telegram ID администратора
        comment: Комментарий администратора (опционально)

    Returns:
        True если успешно, False в противном случае
    """
    session = SessionLocal()
    try:
        verification = session.query(DeadlineVerification).filter_by(id=verification_id, status="pending").first()
        if not verification:
            return False

        deadline = session.query(Deadline).filter_by(id=verification.deadline_id).first()
        if not deadline:
            return False

        # Обновляем запрос на проверку
        verification.status = "approved"
        verification.verified_by = admin_telegram_id
        verification.verified_at = datetime.now(UTC)
        if comment:
            verification.admin_comment = comment

        # Меняем статус дедлайна на "завершен"
        deadline.status = DeadlineStatus.COMPLETED
        deadline.updated_at = datetime.now(UTC)

        session.commit()
        return True
    except Exception as e:
        session.rollback()
        from logging import getLogger
        logger = getLogger(__name__)
        logger.error(f"Ошибка при одобрении проверки: {e}", exc_info=True)
        return False
    finally:
        session.close()


def reject_deadline_verification(verification_id: int, admin_telegram_id: int, comment: str | None = None) -> bool:
    """
    Отклонить выполнение дедлайна.

    Args:
        verification_id: ID запроса на проверку
        admin_telegram_id: Telegram ID администратора
        comment: Комментарий администратора (опционально)

    Returns:
        True если успешно, False в противном случае
    """
    session = SessionLocal()
    try:
        verification = session.query(DeadlineVerification).filter_by(id=verification_id, status="pending").first()
        if not verification:
            return False

        deadline = session.query(Deadline).filter_by(id=verification.deadline_id).first()
        if not deadline:
            return False

        # Обновляем запрос на проверку
        verification.status = "rejected"
        verification.verified_by = admin_telegram_id
        verification.verified_at = datetime.now(UTC)
        if comment:
            verification.admin_comment = comment

        # Возвращаем статус дедлайна на "активен"
        deadline.status = DeadlineStatus.ACTIVE
        deadline.updated_at = datetime.now(UTC)

        session.commit()
        return True
    except Exception as e:
        session.rollback()
        from logging import getLogger
        logger = getLogger(__name__)
        logger.error(f"Ошибка при отклонении проверки: {e}", exc_info=True)
        return False
    finally:
        session.close()


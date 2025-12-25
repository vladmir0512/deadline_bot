from __future__ import annotations

"""
Модели данных для бота дедлайнов.

Таблицы:
- users: информация о пользователе Telegram
- deadlines: дедлайны, связанные с пользователями
- subscriptions: настройки подписок на уведомления
- blocked_users: список заблокированных пользователей
"""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


def utc_now() -> datetime:
    """Возвращает текущее время в UTC."""
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    deadlines: Mapped[list["Deadline"]] = relationship(
        "Deadline",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class DeadlineStatus:
    """Простые статусы дедлайна."""

    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELED = "canceled"
    PENDING_VERIFICATION = "pending_verification"  # На проверке у админа


class Deadline(Base):
    __tablename__ = "deadlines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Связь по пользователю. В плане указан user_identifier, но в БД лучше хранить внешний ключ на users.id
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=DeadlineStatus.ACTIVE, nullable=False, index=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)  # Уникальный ID из внешнего источника

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    # Время последнего отправленного уведомления (для предотвращения дублирования)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="deadlines")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    # Например: "telegram", "email", "daily", "weekly" — можно детализировать позже
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(default=True, nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="subscriptions")


class BlockedUser(Base):
    __tablename__ = "blocked_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)

    # Причина блокировки (опционально)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Кто заблокировал (ID администратора)
    blocked_by: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class UserNotificationSettings(Base):
    """Настройки уведомлений для каждого пользователя."""

    __tablename__ = "user_notification_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True, index=True)

    # Основные настройки
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notification_hour: Mapped[int] = mapped_column(Integer, default=9, nullable=False)  # Час отправки (0-23)

    # Тихий режим (часы когда не отправлять уведомления)
    quiet_hours_start: Mapped[str] = mapped_column(String(5), default="22:00", nullable=False)  # Начало тихого режима (HH:MM)
    quiet_hours_end: Mapped[str] = mapped_column(String(5), default="08:00", nullable=False)    # Конец тихого режима (HH:MM)

    # Типы уведомлений
    daily_reminders: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    weekly_reminders: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    halfway_reminders: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Дни недели для еженедельных напоминаний (JSON строка с массивом номеров дней 0-6, где 0=понедельник)
    weekly_days: Mapped[str] = mapped_column(String(255), default="[0,1,2,3,4]", nullable=False)

    # Предупреждение за N дней до дедлайна
    days_before_warning: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Связи
    user: Mapped["User"] = relationship("User", back_populates="notification_settings")


# Добавить обратную связь в модель User
User.notification_settings: Mapped["UserNotificationSettings | None"] = relationship(
    "UserNotificationSettings",
    back_populates="user",
    uselist=False,  # Один к одному
)


class DeadlineVerification(Base):
    """Запросы на проверку выполнения дедлайна."""

    __tablename__ = "deadline_verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    deadline_id: Mapped[int] = mapped_column(ForeignKey("deadlines.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    
    # Статус проверки: "pending" - ожидает проверки, "approved" - одобрено, "rejected" - отклонено
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    
    # Комментарий пользователя при запросе проверки
    user_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Комментарий админа при проверке
    admin_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Кто проверил (ID администратора)
    verified_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Связи
    deadline: Mapped["Deadline"] = relationship("Deadline")
    user: Mapped["User"] = relationship("User")


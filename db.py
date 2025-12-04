from __future__ import annotations

"""
Базовая настройка SQLAlchemy и подключение к SQLite.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""


def get_database_url() -> str:
    # Берём URL БД из переменной окружения, по умолчанию локальный SQLite файл.
    return os.getenv("DATABASE_URL", "sqlite:///deadlines.db")


# echo=True можно включить при отладке, чтобы видеть SQL-запросы
engine = create_engine(get_database_url(), echo=False)

# expire_on_commit=False оставляет данные в объектах после коммита
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    """
    Простейшая «инициализация миграций»:
    создаёт все таблицы, описанные через Base.metadata.
    Для реального проекта позже можно добавить Alembic.
    """
    from models import User, Deadline, Subscription  # noqa: F401

    Base.metadata.create_all(bind=engine)



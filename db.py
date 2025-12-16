from __future__ import annotations

"""
Базовая настройка SQLAlchemy и подключение к SQLite.
"""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""


def get_database_url() -> str:
    """
    Получить URL базы данных.
    
    Если DATABASE_URL не задан в переменных окружения, использует путь ../data/моя_база.db
    и создаёт каталог ../data/ если его нет.
    """
    db_url = os.getenv("DATABASE_URL")
    
    if db_url:
        # Если URL задан в переменных окружения, используем его
        # Для SQLite путей создаём каталог если нужно
        if db_url.startswith("sqlite:///"):
            db_path = db_url.replace("sqlite:///", "")
            # Если это относительный путь, создаём каталог
            if not os.path.isabs(db_path):
                db_path_obj = Path(db_path)
                db_path_obj.parent.mkdir(parents=True, exist_ok=True)
        return db_url
    
    # По умолчанию используем ../data/моя_база.db
    default_db_path = Path(__file__).parent.parent / "data" / "deadlines.db"
    default_db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Для SQLite используем абсолютный путь для надежности
    # В Windows нужно заменить обратные слеши на прямые
    absolute_path = str(default_db_path.resolve()).replace("\\", "/")
    return f"sqlite:///{absolute_path}"


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



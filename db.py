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

    Учитывает Docker окружение и создаёт правильный путь к БД.
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

                # В Docker контейнере (когда WORKDIR=/app) используем /app/data/
                # Вне контейнера используем текущую логику
                if os.getcwd().startswith('/app'):
                    # Мы в Docker контейнере
                    db_path_obj = Path('/app') / db_path_obj
                    db_path_obj.parent.mkdir(parents=True, exist_ok=True)
                    return f"sqlite:///{db_path_obj}"

                try:
                    db_path_obj.parent.mkdir(parents=True, exist_ok=True)
                except PermissionError:
                    # Если нет прав на создание родительской директории,
                    # используем текущую директорию
                    db_path_obj = Path.cwd() / db_path_obj.name
                    db_path_obj.parent.mkdir(parents=True, exist_ok=True)
                    db_url = f"sqlite:///{db_path_obj}"
        return db_url

    # По умолчанию используем data/deadlines.db относительно текущей директории
    # В Docker используем /app/data/, вне Docker - текущую директорию
    if os.getcwd().startswith('/app'):
        # Docker окружение
        default_db_path = Path('/app/data/deadlines.db')
    else:
        # Локальное окружение
        default_db_path = Path.cwd() / "data" / "deadlines.db"

    try:
        default_db_path.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # Если нет прав, используем текущую директорию
        default_db_path = Path.cwd() / "deadlines.db"

    return f"sqlite:///{default_db_path}"


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



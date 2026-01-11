#!/usr/bin/env python3
"""
Скрипт для создания миграций базы данных, аналогичный Django makemigrations.

Этот скрипт анализирует текущие модели SQLAlchemy и генерирует SQL-скрипты
для создания таблиц, если они еще не существуют.

Использование:
    python scripts/makemigrations.py [message]

Аргументы:
    message - опциональное сообщение для миграции (по умолчанию "Auto-generated migration")
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List

# Добавляем корневую директорию в путь для импортов
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.sql import text

from db import Base, get_database_url
from models import User, Deadline, Subscription, BlockedUser, UserNotificationSettings, DeadlineVerification  # noqa: F401


def get_existing_tables(engine) -> set:
    """Получить список существующих таблиц в базе данных."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        return {row[0] for row in result}


def get_existing_indexes(engine) -> set:
    """Получить список существующих индексов в базе данных."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"))
        return {row[0] for row in result}


def generate_migration_sql(engine) -> List[str]:
    """
    Генерировать SQL для создания отсутствующих таблиц и индексов.

    Возвращает список SQL-команд.
    """
    existing_tables = get_existing_tables(engine)
    existing_indexes = get_existing_indexes(engine)

    table_commands = []
    index_commands = []

    # Получаем все таблицы из метаданных
    for table_name, table in Base.metadata.tables.items():
        if table_name in existing_tables:
            continue  # Таблица уже существует
        # Генерируем SQL для создания таблицы
        create_table_sql = str(CreateTable(table).compile(engine))
        table_commands.append(create_table_sql)

        # Генерируем SQL для индексов таблицы (исключая первичные ключи)
        for index in table.indexes:
            if index.name and index.name not in existing_indexes:
                # Пропускаем индексы для первичных ключей
                if len(index.columns) == 1 and index.columns[0].primary_key:
                    continue
                create_index_sql = str(CreateIndex(index).compile(engine))
                index_commands.append(create_index_sql)

    # Сначала создаем таблицы, затем индексы
    return table_commands + index_commands


def create_migration_file(sql_commands: List[str], message: str = "Auto-generated migration") -> str:
    """
    Создать файл миграции с SQL-командами.

    Возвращает имя созданного файла.
    """
    # Создаем директорию migrations если не существует
    migrations_dir = Path("migrations")
    migrations_dir.mkdir(exist_ok=True)

    # Генерируем имя файла с timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{message.replace(' ', '_').lower()}.sql"
    filepath = migrations_dir / filename

    # Пишем SQL в файл
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("-- Migration generated at {}\n".format(datetime.now().isoformat()))
        f.write(f"-- Message: {message}\n\n")

        for sql in sql_commands:
            f.write(sql + ";\n\n")

    return filename


def main():
    """Основная функция скрипта."""
    # Парсим аргументы
    message = "Auto-generated migration"
    if len(sys.argv) > 1:
        message = " ".join(sys.argv[1:])

    print("Анализ моделей и базы данных...")

    # Получаем URL базы данных
    db_url = get_database_url()
    print(f"База данных: {db_url}")

    # Создаем engine (без echo для чистоты вывода)
    engine = create_engine(db_url, echo=False)

    # Генерируем SQL для миграции
    sql_commands = generate_migration_sql(engine)

    if not sql_commands:
        print("Нет изменений для миграции. Все таблицы уже существуют.")
        return

    print(f"Найдено {len(sql_commands)} SQL-команд для выполнения")

    # Создаем файл миграции
    filename = create_migration_file(sql_commands, message)

    print(f"Миграция создана: migrations/{filename}")
    print("\nДля применения миграции выполните:")
    print("   python scripts/migrate.py")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Скрипт для применения миграций базы данных, аналогичный Django migrate.

Этот скрипт находит и применяет все непрошенные миграции из директории migrations/.

Использование:
    python scripts/migrate.py
"""

import os
import sys
from pathlib import Path
from typing import List

# Добавляем корневую директорию в путь для импортов
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text

from db import get_database_url


def get_applied_migrations(engine) -> set:
    """Получить список уже примененных миграций."""
    applied = set()

    # Проверяем, существует ли таблица __migrations__
    with engine.connect() as conn:
        try:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='__migrations__'"))
            if not result.fetchone():
                # Таблица не существует, создаем ее
                conn.execute(text("""
                    CREATE TABLE __migrations__ (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(255) NOT NULL UNIQUE,
                        applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.commit()
                return applied

            # Получаем список примененных миграций
            result = conn.execute(text("SELECT name FROM __migrations__"))
            applied = {row[0] for row in result}

        except Exception as e:
            print(f"Ошибка при проверке таблицы миграций: {e}")
            # Если ошибка, предполагаем что миграции не применялись
            pass

    return applied


def get_migration_files() -> List[Path]:
    """Получить список файлов миграций, отсортированных по имени."""
    migrations_dir = Path("migrations")

    if not migrations_dir.exists():
        print("❌ Директория migrations не найдена")
        return []

    migration_files = []
    for file in migrations_dir.glob("*.sql"):
        migration_files.append(file)

    # Сортируем по имени файла (timestamp в начале)
    migration_files.sort(key=lambda x: x.name)

    return migration_files


def apply_migration(engine, migration_file: Path) -> bool:
    """Применить одну миграцию."""
    migration_name = migration_file.name

    print(f"Применение миграции: {migration_name}")

    try:
        # Читаем SQL из файла
        with open(migration_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # Разделяем на отдельные команды, игнорируя комментарии и пустые строки
        raw_commands = sql_content.split(';')
        commands = []
        for cmd in raw_commands:
            cmd = cmd.strip()
            if cmd and not cmd.startswith('--'):
                commands.append(cmd)

        with engine.connect() as conn:
            # Начинаем транзакцию
            trans = conn.begin()

            try:
                # Выполняем каждую команду
                for command in commands:
                    if command:
                        try:
                            conn.execute(text(command))
                        except Exception as cmd_error:
                            # Проверяем, является ли ошибка "уже существует"
                            error_msg = str(cmd_error).lower()
                            if any(phrase in error_msg for phrase in [
                                'already exists',
                                'table already exists',
                                'index already exists',
                                'column already exists'
                            ]):
                                print(f"  Пропускаем: объект уже существует ({command[:50]}...)")
                                continue
                            else:
                                # Другая ошибка - пробрасываем
                                raise cmd_error

                # Записываем миграцию как примененную
                conn.execute(text("INSERT INTO __migrations__ (name) VALUES (:name)"), {"name": migration_name})

                # Коммитим транзакцию
                trans.commit()

                print(f"Миграция {migration_name} применена успешно")
                return True

            except Exception as e:
                trans.rollback()
                print(f"Ошибка при применении миграции {migration_name}: {e}")
                return False

    except Exception as e:
        print(f"Ошибка чтения файла миграции {migration_name}: {e}")
        return False


def main():
    """Основная функция скрипта."""
    print("Применение миграций базы данных")
    print("=" * 40)

    # Получаем URL базы данных
    db_url = get_database_url()
    print(f"База данных: {db_url}")

    # Создаем engine
    engine = create_engine(db_url, echo=False)

    # Получаем список примененных миграций
    applied_migrations = get_applied_migrations(engine)
    print(f"Уже применено миграций: {len(applied_migrations)}")

    # Получаем список файлов миграций
    migration_files = get_migration_files()
    if not migration_files:
        print("Нет файлов миграций для применения")
        return

    print(f"Найдено файлов миграций: {len(migration_files)}")

    # Фильтруем только новые миграции
    new_migrations = [f for f in migration_files if f.name not in applied_migrations]

    if not new_migrations:
        print("Все миграции уже применены")
        return

    print(f"Будет применено миграций: {len(new_migrations)}")

    # Применяем новые миграции
    applied_count = 0
    for migration_file in new_migrations:
        if apply_migration(engine, migration_file):
            applied_count += 1
        else:
            print("Применение миграций остановлено из-за ошибки")
            break

    print(f"\nРезультат: применено {applied_count} из {len(new_migrations)} миграций")

    if applied_count == len(new_migrations):
        print("Все миграции применены успешно!")
    else:
        print("Некоторые миграции не были применены")


if __name__ == "__main__":
    main()
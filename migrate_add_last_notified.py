"""
Миграция: добавление колонки last_notified_at в таблицу deadlines.

Запуск:
    python migrate_add_last_notified.py
"""

import os
import sqlite3
import sys
from pathlib import Path


def migrate() -> None:
    """Добавить колонку last_notified_at в таблицу deadlines."""
    # Получаем путь к БД из переменной окружения или используем значение по умолчанию
    db_url = os.getenv("DATABASE_URL", "sqlite:///deadlines.db")
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
    else:
        print(f"❌ Неподдерживаемый формат БД: {db_url}")
        sys.exit(1)

    db_file = Path(db_path)
    if not db_file.exists():
        print(f"❌ Файл БД не найден: {db_path}")
        print("   Запустите сначала: python init_db.py")
        sys.exit(1)

    print(f"📦 Подключение к БД: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Проверяем, существует ли уже колонка
        cursor.execute("PRAGMA table_info(deadlines)")
        columns = [row[1] for row in cursor.fetchall()]

        if "last_notified_at" in columns:
            print("✅ Колонка last_notified_at уже существует")
            conn.close()
            return

        # Добавляем колонку
        print("🔄 Добавление колонки last_notified_at...")
        cursor.execute(
            "ALTER TABLE deadlines ADD COLUMN last_notified_at DATETIME"
        )
        conn.commit()

        print("✅ Колонка last_notified_at успешно добавлена")
        conn.close()

    except sqlite3.Error as e:
        print(f"❌ Ошибка при миграции: {e}")
        sys.exit(1)


if __name__ == "__main__":
    migrate()


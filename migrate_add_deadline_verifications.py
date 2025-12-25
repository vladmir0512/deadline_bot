"""
Миграция: добавление таблицы deadline_verifications для запросов на проверку дедлайнов.

Запуск:
    python migrate_add_deadline_verifications.py
"""

import os
import sqlite3
import sys
from pathlib import Path

def migrate() -> None:
    """Добавить таблицу deadline_verifications."""
    # Получаем путь к БД из переменной окружения или используем значение по умолчанию
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        # По умолчанию используем data/deadlines.db
        default_db_path = Path(__file__).parent / "data" / "deadlines.db"
        db_path = str(default_db_path.resolve())
    elif db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        # Если это относительный путь, преобразуем в абсолютный
        if not os.path.isabs(db_path):
            db_path = str(Path(db_path).resolve())
    else:
        print(f"❌ Неподдерживаемый формат БД: {db_url}")
        sys.exit(1)

    db_file = Path(db_path)
    if not db_file.exists():
        print(f"❌ Файл БД не найден: {db_path}")
        print("   Запустите сначала: python scripts/init_db.py")
        sys.exit(1)

    print(f"[+] Подключение к БД: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Проверяем, существует ли уже таблица
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='deadline_verifications'")
        table_exists = cursor.fetchone()

        if table_exists:
            print("[OK] Таблица deadline_verifications уже существует")
            conn.close()
            return

        print("[+] Создание таблицы deadline_verifications...")

        # Создаем таблицу deadline_verifications
        cursor.execute("""
            CREATE TABLE deadline_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deadline_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'pending',
                user_comment TEXT,
                admin_comment TEXT,
                verified_by INTEGER,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                verified_at DATETIME,
                FOREIGN KEY (deadline_id) REFERENCES deadlines(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Создаем индексы
        cursor.execute("CREATE INDEX idx_deadline_verifications_deadline_id ON deadline_verifications(deadline_id)")
        cursor.execute("CREATE INDEX idx_deadline_verifications_user_id ON deadline_verifications(user_id)")
        cursor.execute("CREATE INDEX idx_deadline_verifications_status ON deadline_verifications(status)")

        conn.commit()
        print("[OK] Таблица deadline_verifications создана успешно")

        conn.close()

    except sqlite3.Error as e:
        print(f"❌ Ошибка при создании таблицы: {e}")
        sys.exit(1)


if __name__ == "__main__":
    migrate()


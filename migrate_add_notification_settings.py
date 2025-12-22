"""
Миграция: добавление таблицы user_notification_settings.

Запуск:
    python migrate_add_notification_settings.py
"""

import os
import sqlite3
import sys
from pathlib import Path

def migrate() -> None:
    """Добавить таблицу user_notification_settings."""
    # Получаем путь к БД из переменной окружения или используем значение по умолчанию
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        # По умолчанию используем ../data/моя_база.db
        default_db_path = Path(__file__).parent.parent / "data" / "deadlines.db"
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
        print("   Запустите сначала: python init_db.py")
        sys.exit(1)

    print(f"[+] Подключение к БД: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Проверяем, существует ли уже таблица
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_notification_settings'")
        table_exists = cursor.fetchone()

        if table_exists:
            print("[OK] Таблица user_notification_settings уже существует")
            conn.close()
            return

        # Создаем таблицу
        print("[+] Создание таблицы user_notification_settings...")
        cursor.execute("""
            CREATE TABLE user_notification_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                notifications_enabled BOOLEAN DEFAULT 1,
                notification_hour INTEGER DEFAULT 9,
                timezone TEXT DEFAULT 'Europe/Moscow',
                daily_reminders BOOLEAN DEFAULT 1,
                weekly_reminders BOOLEAN DEFAULT 1,
                halfway_reminders BOOLEAN DEFAULT 1,
                weekly_days TEXT DEFAULT '[1,2,3,4,5]',
                days_before_warning INTEGER DEFAULT 1,
                quiet_hours_start TEXT DEFAULT '22:00',
                quiet_hours_end TEXT DEFAULT '08:00',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id)
            )
        """)

        # Создаем индекс для быстрого поиска по user_id
        cursor.execute("""
            CREATE INDEX idx_user_notification_settings_user_id
            ON user_notification_settings(user_id)
        """)

        # Заполняем таблицу настройками по умолчанию для существующих пользователей
        print("[+] Заполнение настроек по умолчанию для существующих пользователей...")
        cursor.execute("""
            INSERT INTO user_notification_settings (
                user_id, notifications_enabled, notification_hour, timezone,
                daily_reminders, weekly_reminders, halfway_reminders,
                weekly_days, days_before_warning, quiet_hours_start, quiet_hours_end
            )
            SELECT
                u.id, 1, 9, 'Europe/Moscow', 1, 1, 1, '[1,2,3,4,5]', 1, '22:00', '08:00'
            FROM users u
            LEFT JOIN user_notification_settings uns ON u.id = uns.user_id
            WHERE uns.user_id IS NULL
        """)

        conn.commit()
        print("[OK] Таблица user_notification_settings успешно создана и заполнена")

        # Проверяем количество созданных записей
        cursor.execute("SELECT COUNT(*) FROM user_notification_settings")
        count = cursor.fetchone()[0]
        print(f"[INFO] Создано {count} записей настроек по умолчанию")

        conn.close()

    except sqlite3.Error as e:
        print(f"[ERROR] Ошибка при миграции: {e}")
        sys.exit(1)


if __name__ == "__main__":
    migrate()
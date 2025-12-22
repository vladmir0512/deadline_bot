"""
Миграция: обновление таблицы user_notification_settings (изменение полей quiet_hours).
"""

import os
import sqlite3
import sys
from pathlib import Path

def migrate() -> None:
    """Обновить таблицу user_notification_settings."""
    # Получаем путь к БД из переменной окружения или используем значение по умолчанию
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        # По умолчанию используем ../data/deadlines.db
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

        # Проверяем, существует ли таблица
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_notification_settings'")
        table_exists = cursor.fetchone()

        if not table_exists:
            print("[!] Таблица user_notification_settings не существует")
            print("   Сначала запустите: python migrate_add_notification_settings.py")
            sys.exit(1)

        # Проверяем структуру таблицы
        cursor.execute("PRAGMA table_info(user_notification_settings)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        print("[+] Текущая структура таблицы:")
        for col in columns:
            print(f"   {col[1]}: {col[2]} {'NULL' if col[3] else 'NOT NULL'} DEFAULT {col[4]}")

        # Проверяем типы полей quiet_hours
        quiet_start_type = None
        quiet_end_type = None

        for col in columns:
            if col[1] == 'quiet_hours_start':
                quiet_start_type = col[2]
            elif col[1] == 'quiet_hours_end':
                quiet_end_type = col[2]

        needs_migration = False
        if quiet_start_type != 'VARCHAR(5)' or quiet_end_type != 'VARCHAR(5)':
            needs_migration = True
            print(f"[!] Требуется миграция: quiet_hours_start={quiet_start_type}, quiet_hours_end={quiet_end_type}")

        if not needs_migration:
            print("[OK] Структура таблицы корректна, миграция не требуется")
            conn.close()
            return

        # Создаем новую таблицу с правильной структурой
        print("[+] Создание новой таблицы с правильной структурой...")

        cursor.execute("""
            CREATE TABLE user_notification_settings_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                notifications_enabled BOOLEAN DEFAULT 1,
                notification_hour INTEGER DEFAULT 9,
                daily_reminders BOOLEAN DEFAULT 1,
                weekly_reminders BOOLEAN DEFAULT 1,
                halfway_reminders BOOLEAN DEFAULT 1,
                weekly_days TEXT DEFAULT '[1,2,3,4,5]',
                days_before_warning INTEGER DEFAULT 1,
                quiet_hours_start VARCHAR(5) DEFAULT '22:00',
                quiet_hours_end VARCHAR(5) DEFAULT '08:00',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id)
            )
        """)

        # Копируем данные из старой таблицы в новую
        print("[+] Копирование данных...")
        cursor.execute("""
            INSERT INTO user_notification_settings_new (
                id, user_id, notifications_enabled, notification_hour,
                daily_reminders, weekly_reminders, halfway_reminders,
                weekly_days, days_before_warning,
                quiet_hours_start, quiet_hours_end,
                created_at, updated_at
            )
            SELECT
                id, user_id, notifications_enabled, notification_hour,
                daily_reminders, weekly_reminders, halfway_reminders,
                weekly_days, days_before_warning,
                '22:00', '08:00',  -- Значения по умолчанию для тихого режима
                created_at, updated_at
            FROM user_notification_settings
        """)

        # Удаляем старую таблицу
        print("[+] Удаление старой таблицы...")
        cursor.execute("DROP TABLE user_notification_settings")

        # Переименовываем новую таблицу
        print("[+] Переименование новой таблицы...")
        cursor.execute("ALTER TABLE user_notification_settings_new RENAME TO user_notification_settings")

        # Создаем индекс
        cursor.execute("""
            CREATE INDEX idx_user_notification_settings_user_id
            ON user_notification_settings(user_id)
        """)

        # Проверяем количество перенесенных записей
        cursor.execute("SELECT COUNT(*) FROM user_notification_settings")
        count = cursor.fetchone()[0]
        print(f"[INFO] Перенесено {count} записей настроек")

        conn.commit()
        print("[OK] Миграция успешно завершена")

        conn.close()

    except sqlite3.Error as e:
        print(f"[ERROR] Ошибка при миграции: {e}")
        sys.exit(1)


if __name__ == "__main__":
    migrate()

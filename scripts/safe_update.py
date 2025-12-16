#!/usr/bin/env python3
"""
Безопасное обновление приложения с сохранением пользовательских данных.

Этот скрипт выполняет:
1. Создание резервной копии базы данных
2. Проверку совместимости новой версии
3. Применение миграций БД (если нужны)
4. Восстановление при неудаче

Использование:
    python scripts/safe_update.py              # Полное безопасное обновление
    python scripts/safe_update.py --rollback   # Откат к предыдущей версии
    python scripts/safe_update.py --check      # Проверить состояние перед обновлением
"""

import argparse
import sys
import time
from pathlib import Path
from datetime import datetime

# Добавляем корневую директорию в путь для импортов
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import SessionLocal, engine
from version import get_version


class SafeUpdater:
    """Класс для безопасного обновления приложения."""

    def __init__(self):
        self.backup_dir = Path("data/backups")
        self.rollback_marker = Path("data/.rollback_available")
        self.update_log = Path("logs/update.log")

    def log(self, message: str):
        """Логирует сообщение."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"

        print(log_message)

        # Записываем в лог файл
        try:
            with open(self.update_log, 'a', encoding='utf-8') as f:
                f.write(log_message + '\n')
        except Exception:
            pass  # Игнорируем ошибки записи в лог

    def create_backup(self) -> str:
        """Создает резервную копию перед обновлением."""
        self.log("📦 Создание резервной копии базы данных...")

        try:
            from scripts.backup_db import create_backup
            backup_file = create_backup(self.backup_dir)

            if backup_file:
                self.log(f"✅ Резервная копия создана: {backup_file}")

                # Сохраняем информацию о бэкапе для возможного отката
                with open(self.rollback_marker, 'w', encoding='utf-8') as f:
                    f.write(f"backup_file={backup_file}\n")
                    f.write(f"timestamp={datetime.now().isoformat()}\n")
                    f.write(f"version={get_version()}\n")

                return backup_file
            else:
                raise Exception("Не удалось создать резервную копию")

        except Exception as e:
            self.log(f"❌ Ошибка создания бэкапа: {e}")
            raise

    def check_database_integrity(self) -> bool:
        """Проверяет целостность базы данных."""
        self.log("🔍 Проверка целостности базы данных...")

        try:
            with engine.connect() as conn:
                # Проверяем основные таблицы
                result = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in result.fetchall()]

                required_tables = ['users', 'deadlines', 'subscriptions']
                missing_tables = [t for t in required_tables if t not in tables]

                if missing_tables:
                    self.log(f"❌ Отсутствуют таблицы: {missing_tables}")
                    return False

                # Проверяем количество записей
                for table in required_tables:
                    result = conn.execute(f"SELECT COUNT(*) FROM {table}")
                    count = result.fetchone()[0]
                    self.log(f"📊 Таблица {table}: {count} записей")

                self.log("✅ Целостность базы данных подтверждена")
                return True

        except Exception as e:
            self.log(f"❌ Ошибка проверки БД: {e}")
            return False

    def run_migrations(self) -> bool:
        """Применяет миграции базы данных."""
        self.log("🔄 Проверка и применение миграций...")

        try:
            # Проверяем, настроен ли Alembic
            migrations_dir = Path("migrations")
            if not migrations_dir.exists():
                self.log("⚠️  Alembic не настроен, пропускаем миграции")
                return True

            # Проверяем статус миграций
            import subprocess
            result = subprocess.run(
                ["alembic", "current"],
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )

            if result.returncode == 0:
                self.log("✅ Миграции в актуальном состоянии")
                return True
            else:
                self.log("📝 Применение отложенных миграций...")
                result = subprocess.run(
                    ["alembic", "upgrade", "head"],
                    capture_output=True,
                    text=True,
                    cwd=Path.cwd()
                )

                if result.returncode == 0:
                    self.log("✅ Миграции применены успешно")
                    return True
                else:
                    self.log(f"❌ Ошибка применения миграций: {result.stderr}")
                    return False

        except Exception as e:
            self.log(f"❌ Ошибка работы с миграциями: {e}")
            return False

    def test_application(self) -> bool:
        """Тестирует работу приложения после обновления."""
        self.log("🧪 Тестирование приложения...")

        try:
            # Импортируем основные модули для проверки
            import bot
            import healthcheck
            from db import SessionLocal

            # Проверяем подключение к БД
            with SessionLocal() as session:
                session.execute("SELECT 1")

            self.log("✅ Приложение прошло базовое тестирование")
            return True

        except Exception as e:
            self.log(f"❌ Ошибка тестирования приложения: {e}")
            return False

    def rollback(self) -> bool:
        """Откатывает обновление к предыдущей версии."""
        self.log("🔄 Выполнение отката к предыдущей версии...")

        if not self.rollback_marker.exists():
            self.log("❌ Информация об откате недоступна")
            return False

        try:
            # Читаем информацию об откате
            rollback_info = {}
            with open(self.rollback_marker, 'r', encoding='utf-8') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        rollback_info[key] = value

            backup_file = rollback_info.get('backup_file')
            if not backup_file or not Path(backup_file).exists():
                self.log("❌ Файл резервной копии не найден")
                return False

            # Восстанавливаем из бэкапа
            self.log(f"📦 Восстановление из: {backup_file}")
            from scripts.backup_db import restore_backup
            if restore_backup(backup_file):
                self.log("✅ Откат выполнен успешно")

                # Удаляем маркер отката
                self.rollback_marker.unlink()
                return True
            else:
                self.log("❌ Ошибка восстановления из бэкапа")
                return False

        except Exception as e:
            self.log(f"❌ Ошибка отката: {e}")
            return False

    def update(self) -> bool:
        """Выполняет полное безопасное обновление."""
        self.log(f"🚀 Начало обновления до версии {get_version()}")
        start_time = time.time()

        try:
            # Шаг 1: Проверка целостности
            if not self.check_database_integrity():
                return False

            # Шаг 2: Создание резервной копии
            backup_file = self.create_backup()

            # Шаг 3: Применение миграций
            if not self.run_migrations():
                self.log("❌ Ошибка миграций, начинаем откат...")
                self.rollback()
                return False

            # Шаг 4: Тестирование
            if not self.test_application():
                self.log("❌ Ошибка тестирования, начинаем откат...")
                self.rollback()
                return False

            # Шаг 5: Финализация
            elapsed = time.time() - start_time
            self.log(".1f"
            return True

        except Exception as e:
            self.log(f"❌ Критическая ошибка обновления: {e}")
            self.log("🔄 Попытка отката...")
            self.rollback()
            return False

    def check_status(self) -> None:
        """Проверяет состояние системы перед обновлением."""
        self.log("📊 Проверка состояния системы...")

        # Версия приложения
        self.log(f"📦 Текущая версия: {get_version()}")

        # Состояние базы данных
        self.check_database_integrity()

        # Проверка бэкапов
        if self.backup_dir.exists():
            backups = list(self.backup_dir.glob("backup_*.db"))
            self.log(f"💾 Доступно резервных копий: {len(backups)}")
            if backups:
                latest = max(backups, key=lambda x: x.stat().st_mtime)
                self.log(f"📅 Последний бэкап: {latest.name}")
        else:
            self.log("⚠️  Резервные копии не найдены")

        # Проверка rollback маркера
        if self.rollback_marker.exists():
            self.log("🔄 Доступен откат к предыдущей версии")
        else:
            self.log("ℹ️  Откат недоступен")


def main():
    parser = argparse.ArgumentParser(description="Безопасное обновление приложения")
    parser.add_argument("--rollback", action="store_true", help="Откат к предыдущей версии")
    parser.add_argument("--check", action="store_true", help="Проверить состояние перед обновлением")

    args = parser.parse_args()
    updater = SafeUpdater()

    if args.rollback:
        success = updater.rollback()
        sys.exit(0 if success else 1)
    elif args.check:
        updater.check_status()
        sys.exit(0)
    else:
        success = updater.update()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Скрипт для создания резервных копий базы данных.

Использование:
    python scripts/backup_db.py              # Создать бэкап с текущим timestamp
    python scripts/backup_db.py --restore backup_20241216_143000.db  # Восстановить из бэкапа
    python scripts/backup_db.py --list       # Показать доступные бэкапы
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Добавляем корневую директорию в путь для импортов
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import SessionLocal, engine
from models import Base
import os


def create_backup(backup_dir: Path = None) -> str:
    """Создает резервную копию базы данных."""
    if backup_dir is None:
        backup_dir = Path("data/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Генерируем имя файла с timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"backup_{timestamp}.db"

    print(f"📦 Создание резервной копии: {backup_file}")

    try:
        # Используем SQLite backup API
        with engine.connect() as conn:
            conn.execute(f"VACUUM INTO '{backup_file}'")
            print(f"✅ Резервная копия создана: {backup_file}")
            return str(backup_file)
    except Exception as e:
        print(f"❌ Ошибка при создании бэкапа: {e}")
        return None


def restore_backup(backup_file: str) -> bool:
    """Восстанавливает базу данных из резервной копии."""
    backup_path = Path(backup_file)
    if not backup_path.exists():
        print(f"❌ Файл бэкапа не найден: {backup_file}")
        return False

    db_path = Path("data/deadlines.db")
    backup_db_path = db_path.with_suffix('.backup')

    print(f"🔄 Восстановление из: {backup_file}")
    print(f"📍 Целевая БД: {db_path}")

    try:
        # Создаем бэкап текущей БД перед восстановлением
        if db_path.exists():
            create_backup()
            print("📋 Текущая БД сохранена в бэкап")

        # Копируем бэкап на место основной БД
        import shutil
        shutil.copy2(backup_file, db_path)

        print("✅ Восстановление завершено успешно"        return True

    except Exception as e:
        print(f"❌ Ошибка при восстановлении: {e}")
        return False


def list_backups(backup_dir: Path = None) -> None:
    """Показывает список доступных резервных копий."""
    if backup_dir is None:
        backup_dir = Path("data/backups")

    if not backup_dir.exists():
        print("📁 Нет доступных резервных копий")
        return

    backups = list(backup_dir.glob("backup_*.db"))
    backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    if not backups:
        print("📁 Нет доступных резервных копий")
        return

    print("📋 Доступные резервные копии:")
    print("-" * 50)

    for backup in backups[:10]:  # Показываем последние 10
        mtime = datetime.fromtimestamp(backup.stat().st_mtime)
        size = backup.stat().st_size / 1024  # KB
        print(".2f"
def main():
    parser = argparse.ArgumentParser(description="Управление резервными копиями базы данных")
    parser.add_argument("--restore", type=str, help="Восстановить из указанного файла бэкапа")
    parser.add_argument("--list", action="store_true", help="Показать список бэкапов")
    parser.add_argument("--backup-dir", type=str, default="data/backups", help="Директория для бэкапов")

    args = parser.parse_args()
    backup_dir = Path(args.backup_dir)

    if args.list:
        list_backups(backup_dir)
    elif args.restore:
        success = restore_backup(args.restore)
        sys.exit(0 if success else 1)
    else:
        # Создаем бэкап
        backup_file = create_backup(backup_dir)
        if backup_file:
            print(f"💾 Бэкап сохранен: {backup_file}")
            sys.exit(0)
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()

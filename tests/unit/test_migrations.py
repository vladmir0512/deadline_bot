#!/usr/bin/env python3
"""
Тесты для системы миграций базы данных.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from subprocess import run, PIPE

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def test_migration_system():
    """Тестируем создание и применение миграций."""
    print("Тестируем систему миграций...")

    # Создаем временную директорию для тестовой базы
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Пути к тестовой базе и миграциям
        test_db = temp_path / "test_migrations.db"
        test_migrations_dir = temp_path / "migrations"

        # Устанавливаем переменную окружения для базы
        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite:///{test_db}"

        print(f"  Тестовая база: {test_db}")
        print(f"  Директория миграций: {test_migrations_dir}")

        # 1. Проверяем, что на пустой базе makemigrations создаст миграции
        print("  Шаг 1: Создание миграций...")
        result = run([
            sys.executable, str(Path(__file__).parent.parent.parent / "scripts" / "makemigrations.py"), "Test migration"
        ], cwd=temp_path, env=env, capture_output=True, text=True)

        print(f"    Выходной код: {result.returncode}")
        if result.stdout:
            print(f"    stdout: {result.stdout.strip()}")
        if result.stderr:
            print(f"    stderr: {result.stderr.strip()}")

        assert result.returncode == 0, f"makemigrations завершился с ошибкой: {result.stderr}"

        # Проверяем, что создалась директория migrations
        assert test_migrations_dir.exists(), "Директория migrations не создана"
        migration_files = list(test_migrations_dir.glob("*.sql"))
        assert len(migration_files) > 0, "Файлы миграций не созданы"
        print(f"    Создано файлов миграций: {len(migration_files)}")

        # 2. Применяем миграции
        print("  Шаг 2: Применение миграций...")
        result = run([
            sys.executable, str(Path(__file__).parent.parent.parent / "scripts" / "migrate.py")
        ], cwd=temp_path, env=env, capture_output=True, text=True)

        print(f"    Выходной код: {result.returncode}")
        if result.stdout:
            print(f"    stdout: {result.stdout.strip()}")
        if result.stderr:
            print(f"    stderr: {result.stderr.strip()}")

        assert result.returncode == 0, f"migrate завершился с ошибкой: {result.stderr}"

        # Проверяем, что база создана и содержит таблицы
        assert test_db.exists(), "Файл базы данных не создан"
        assert test_db.stat().st_size > 0, "База данных пустая"

        # 3. Повторное применение миграций (должно быть безопасным)
        print("  Шаг 3: Повторное применение миграций...")
        result = run([
            sys.executable, str(Path(__file__).parent.parent.parent / "scripts" / "migrate.py")
        ], cwd=temp_path, env=env, capture_output=True, text=True)

        print(f"    Выходной код: {result.returncode}")
        if result.stdout:
            print(f"    stdout: {result.stdout.strip()}")
        if result.stderr:
            print(f"    stderr: {result.stderr.strip()}")

        assert result.returncode == 0, f"Повторный migrate завершился с ошибкой: {result.stderr}"

        print("  Все тесты миграций пройдены!")

if __name__ == "__main__":
    test_migration_system()
    print("Тесты миграций завершены успешно!")
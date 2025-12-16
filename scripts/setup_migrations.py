#!/usr/bin/env python3
"""
Настройка Alembic для миграций базы данных.

Этот скрипт инициализирует Alembic в проекте и создает начальную миграцию
на основе текущей схемы базы данных.

Использование:
    python scripts/setup_migrations.py    # Настроить Alembic и создать первую миграцию
"""

import subprocess
import sys
from pathlib import Path

# Добавляем корневую директорию в путь для импортов
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import engine
from models import Base


def run_command(cmd: list, cwd: Path = None) -> bool:
    """Выполняет команду и возвращает статус."""
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
        print(f"✅ {cmd[0]} {' '.join(cmd[1:])}")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка выполнения {' '.join(cmd)}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return False


def setup_alembic():
    """Настраивает Alembic для проекта."""
    print("🚀 Настройка Alembic для миграций базы данных")
    print("=" * 50)

    # Создаем директорию для миграций
    migrations_dir = Path("migrations")
    if migrations_dir.exists():
        print("⚠️  Директория migrations уже существует")
        response = input("Перезаписать? (y/N): ").lower().strip()
        if response != 'y':
            print("Отмена настройки")
            return False

        # Удаляем старую директорию
        import shutil
        shutil.rmtree(migrations_dir)

    # Инициализируем Alembic
    print("📁 Создание структуры миграций...")
    if not run_command(["alembic", "init", "migrations"]):
        return False

    # Создаем alembic.ini
    alembic_ini = Path("alembic.ini")
    if alembic_ini.exists():
        # Обновляем конфигурацию
        content = alembic_ini.read_text()

        # Обновляем путь к миграциям
        content = content.replace("script_location = alembic", "script_location = migrations")

        # Добавляем конфигурацию для нашего проекта
        if "sqlalchemy.url" not in content:
            content += "\n\n[alembic]\n" \
                      "sqlalchemy.url = sqlite:///data/deadlines.db\n"

        alembic_ini.write_text(content)
        print("✅ alembic.ini обновлен")

    # Создаем env.py для миграций
    env_py = migrations_dir / "env.py"
    if env_py.exists():
        content = env_py.read_text()

        # Заменяем импорты для нашего проекта
        content = content.replace(
            "from alembic import context",
            "from alembic import context\n"
            "import sys\n"
            "from pathlib import Path\n"
            "sys.path.insert(0, str(Path(__file__).parent.parent))\n"
            "\n"
            "from db import engine\n"
            "from models import Base\n"
        )

        content = content.replace(
            "target_metadata = None",
            "target_metadata = Base.metadata"
        )

        env_py.write_text(content)
        print("✅ env.py настроен для проекта")

    # Создаем первую миграцию на основе текущей схемы
    print("📝 Создание первой миграции...")
    if not run_command(["alembic", "revision", "--autogenerate", "-m", "Initial migration"]):
        return False

    print("✅ Alembic настроен успешно!")
    print("\n📚 Доступные команды:")
    print("  alembic current          # Текущая ревизия")
    print("  alembic history          # История миграций")
    print("  alembic upgrade head     # Применить все миграции")
    print("  alembic downgrade -1     # Откатить последнюю миграцию")
    print("  alembic revision --autogenerate -m 'message'  # Создать новую миграцию")

    return True


if __name__ == "__main__":
    success = setup_alembic()
    sys.exit(0 if success else 1)

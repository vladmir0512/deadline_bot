"""
Небольшой скрипт для инициализации БД (создания таблиц).

Запуск (из активированного виртуального окружения):
    python init_db.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import init_db


def main() -> None:
    init_db()
    print("База данных инициализирована (таблицы созданы, если их ещё не было).")


if __name__ == "__main__":
    main()



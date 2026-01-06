"""
Утилиты для работы с заблокированными пользователями.

Список заблокированных пользователей хранится в файле blocked_users.txt
в корне проекта. Каждый ID на отдельной строке.
"""

import logging
from pathlib import Path
from typing import Set

from db import SessionLocal
from models import User
from services import delete_user

logger = logging.getLogger(__name__)

# Путь к файлу с заблокированными пользователями
BLOCKED_USERS_FILE = Path(__file__).parent / "blocked_users.txt"


def get_blocked_users() -> Set[int]:
    """
    Получить множество заблокированных Telegram ID.

    Returns:
        Set[int]: Множество заблокированных ID
    """
    blocked_users = set()

    try:
        if BLOCKED_USERS_FILE.exists():
            with open(BLOCKED_USERS_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Пропускаем пустые строки и комментарии
                    if not line or line.startswith('#'):
                        continue
                    try:
                        telegram_id = int(line)
                        blocked_users.add(telegram_id)
                    except ValueError:
                        logger.warning(f"Некорректный Telegram ID в файле: {line}")
        else:
            logger.info("Файл blocked_users.txt не найден, создаем пустой")
            BLOCKED_USERS_FILE.touch()

    except Exception as e:
        logger.error(f"Ошибка при чтении файла заблокированных пользователей: {e}")

    return blocked_users


def is_user_blocked(telegram_id: int) -> bool:
    """
    Проверить, заблокирован ли пользователь.

    Args:
        telegram_id: Telegram ID пользователя

    Returns:
        bool: True если пользователь заблокирован
    """
    return telegram_id in get_blocked_users()


def block_user(telegram_id: int) -> bool:
    """
    Заблокировать пользователя.

    Args:
        telegram_id: Telegram ID пользователя для блокировки

    Returns:
        bool: True если успешно заблокирован
    """
    try:
        # Получаем текущий список
        blocked_users = get_blocked_users()

        # Если уже заблокирован, ничего не делаем
        if telegram_id in blocked_users:
            return True

        # Добавляем пользователя
        blocked_users.add(telegram_id)

        # Записываем обратно в файл
        _write_blocked_users_to_file(blocked_users)

        # Пытаемся удалить пользователя из базы данных по telegram_id
        try:
            session = SessionLocal()
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if user:
                success = delete_user(user.id)
                if success:
                    logger.info(f"Пользователь {telegram_id} удален из базы данных при блокировке")
                else:
                    logger.warning(f"Не удалось удалить пользователя {telegram_id} из базы данных")
            else:
                logger.info(f"Пользователь {telegram_id} не найден в базе данных (уже удален или не существовал)")
        except Exception as db_error:
            logger.error(f"Ошибка при удалении пользователя {telegram_id} из базы данных: {db_error}")
        finally:
            session.close()

        logger.info(f"Пользователь {telegram_id} заблокирован")
        return True

    except Exception as e:
        logger.error(f"Ошибка при блокировке пользователя {telegram_id}: {e}")
        return False


def unblock_user(telegram_id: int) -> bool:
    """
    Разблокировать пользователя.

    Args:
        telegram_id: Telegram ID пользователя для разблокировки

    Returns:
        bool: True если успешно разблокирован
    """
    try:
        # Получаем текущий список
        blocked_users = get_blocked_users()

        # Если не заблокирован, ничего не делаем
        if telegram_id not in blocked_users:
            return True

        # Удаляем пользователя
        blocked_users.remove(telegram_id)

        # Записываем обратно в файл
        _write_blocked_users_to_file(blocked_users)

        logger.info(f"Пользователь {telegram_id} разблокирован")
        return True

    except Exception as e:
        logger.error(f"Ошибка при разблокировке пользователя {telegram_id}: {e}")
        return False


def _write_blocked_users_to_file(blocked_users: Set[int]) -> None:
    """
    Записать список заблокированных пользователей в файл.

    Args:
        blocked_users: Множество заблокированных ID
    """
    try:
        # Создаем директорию если не существует
        BLOCKED_USERS_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Сортируем для удобства чтения
        sorted_users = sorted(blocked_users)

        with open(BLOCKED_USERS_FILE, 'w', encoding='utf-8') as f:
            f.write("# Список заблокированных Telegram ID пользователей\n")
            f.write("# Один ID на строку\n")
            f.write("# Формат: telegram_id\n")
            f.write("# Пример:\n")
            f.write("# 123456789\n")
            f.write("# 987654321\n\n")

            for user_id in sorted_users:
                f.write(f"{user_id}\n")

    except Exception as e:
        logger.error(f"Ошибка при записи файла заблокированных пользователей: {e}")
        raise

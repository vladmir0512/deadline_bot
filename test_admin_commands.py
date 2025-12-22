#!/usr/bin/env python3
"""
Тест административных команд блокировки.
"""

import asyncio
import os
from aiogram import Bot
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

from block_utils import get_blocked_users

async def test_admin_commands():
    """Тест административных команд."""

    print("=== ТЕСТ АДМИНИСТРАТИВНЫХ КОМАНД ===")

    # Получаем токен бота
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("TELEGRAM_BOT_TOKEN не найден")
        return

    bot = Bot(token=bot_token)

    try:
        # Получаем список заблокированных
        print("\n1. Получение списка заблокированных...")
        blocked = get_blocked_users()
        print(f"   Текущие заблокированные: {blocked}")

        # Имитируем команду /blocked_users
        print("\n2. Имитация команды /blocked_users...")
        if not blocked:
            message = "Список заблокированных пользователей пуст.\n\nИспользуйте `/block <telegram_id>` для блокировки пользователей."
        else:
            blocked_list = "\n".join(f"• `{user_id}`" for user_id in sorted(blocked))
            message = f"Заблокированные пользователи ({len(blocked)}):\n\n{blocked_list}\n\nИспользуйте `/unblock <telegram_id>` для разблокировки."

        print(f"   Сообщение: {message}")

        # Имитируем команду /block 123456789
        print("\n3. Имитация команды /block 123456789...")
        from block_utils import block_user
        success = block_user(123456789)
        if success:
            print("   Пользователь 123456789 заблокирован")
        else:
            print("   Ошибка при блокировке")

        # Проверяем список после блокировки
        blocked = get_blocked_users()
        print(f"   Список после блокировки: {blocked}")

        # Имитируем команду /unblock 123456789
        print("\n4. Имитация команды /unblock 123456789...")
        from block_utils import unblock_user
        success = unblock_user(123456789)
        if success:
            print("   Пользователь 123456789 разблокирован")
        else:
            print("   Ошибка при разблокировке")

        # Финальная проверка
        blocked = get_blocked_users()
        print(f"   Финальный список: {blocked}")

        print("\n=== ТЕСТ ЗАВЕРШЕН ===")

    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test_admin_commands())

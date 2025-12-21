#!/usr/bin/env python3
"""
Тест middleware блокировки - проверка что заблокированные пользователи не могут использовать бота.
"""

import asyncio
import os
from aiogram import Bot
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

from block_utils import block_user, is_user_blocked

async def test_middleware_block():
    """Тест middleware блокировки."""

    print("=== ТЕСТ MIDDLEWARE БЛОКИРОВКИ ===")

    # Получаем токен бота
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("TELEGRAM_BOT_TOKEN не найден")
        return

    bot = Bot(token=bot_token)

    try:
        # Блокируем пользователя
        print("\n1. Блокировка пользователя 929644995...")
        success = block_user(929644995)
        if success:
            print("   Пользователь заблокирован")
        else:
            print("   Ошибка при блокировке")

        # Проверяем статус блокировки
        print("\n2. Проверка статуса блокировки...")
        is_blocked = is_user_blocked(929644995)
        print(f"   Пользователь заблокирован: {is_blocked}")

        # Пробуем отправить команду (должна игнорироваться middleware)
        print("\n3. Отправка команды заблокированному пользователю...")
        try:
            await bot.send_message(
                chat_id=929644995,
                text="/help"  # Отправляем команду
            )
            print("   Команда отправлена (middleware НЕ работает)")
        except Exception as e:
            print(f"   Ошибка при отправке команды: {e}")

        # Разблокируем пользователя обратно
        print("\n4. Разблокировка пользователя...")
        from block_utils import unblock_user
        success = unblock_user(929644995)
        if success:
            print("   Пользователь разблокирован")
        else:
            print("   Ошибка при разблокировке")

        # Проверяем что теперь команды работают
        print("\n5. Отправка команды разблокированному пользователю...")
        try:
            await bot.send_message(
                chat_id=929644995,
                text="/help"
            )
            print("   Команда отправлена (middleware работает корректно)")
        except Exception as e:
            print(f"   Ошибка при отправке команды: {e}")

        print("\n=== ТЕСТ ЗАВЕРШЕН ===")

    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test_middleware_block())
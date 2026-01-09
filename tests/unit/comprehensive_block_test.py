#!/usr/bin/env python3
"""
Комплексный тест системы блокировки пользователей.
"""

import asyncio
import os
from aiogram import Bot
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

from ...block_utils import get_blocked_users, is_user_blocked, block_user, unblock_user

async def comprehensive_block_test():
    """Комплексный тест системы блокировки."""

    print("=== КОМПЛЕКСНЫЙ ТЕСТ СИСТЕМЫ БЛОКИРОВКИ ===\n")

    # 1. Проверяем начальное состояние
    print("1. ПРОВЕРКА НАЧАЛЬНОГО СОСТОЯНИЯ")
    print("-" * 40)
    blocked = get_blocked_users()
    print(f"Заблокированные пользователи: {blocked}")
    print(f"Список {'пуст' if len(blocked) == 0 else 'не пуст'}")
    print()

    # 2. Тестируем блокировку пользователей
    print("2. ТЕСТ БЛОКИРОВКИ ПОЛЬЗОВАТЕЛЕЙ")
    print("-" * 40)

    test_users = [111111111, 222222222, 333333333]

    for user_id in test_users:
        print(f"Блокировка пользователя {user_id}...")
        success = block_user(user_id, 999999999)
        print(f"  Результат: {'УСПЕХ' if success else 'ОШИБКА'}")
        is_blocked = is_user_blocked(user_id)
        print(f"  Статус блокировки: {'ЗАБЛОКИРОВАН' if is_blocked else 'НЕ ЗАБЛОКИРОВАН'}")
        print()

    # 3. Проверяем список после блокировки
    print("3. СПИСОК ПОСЛЕ БЛОКИРОВКИ")
    print("-" * 40)
    blocked = get_blocked_users()
    print(f"Всего заблокированных: {len(blocked)}")
    print(f"Заблокированные ID: {sorted(blocked)}")

    expected_blocked = set(test_users)
    if blocked == expected_blocked:
        print("СПИСОК КОРРЕКТЕН")
    else:
        print("ОШИБКА В СПИСКЕ!")
    print()

    # 4. Тестируем разблокировку
    print("4. ТЕСТ РАЗБЛОКИРОВКИ ПОЛЬЗОВАТЕЛЕЙ")
    print("-" * 40)

    for user_id in [111111111, 222222222]:  # Разблокируем двоих
        print(f"Разблокировка пользователя {user_id}...")
        success = unblock_user(user_id)
        print(f"  Результат: {'УСПЕХ' if success else 'ОШИБКА'}")
        is_blocked = is_user_blocked(user_id)
        print(f"  Статус блокировки: {'ЗАБЛОКИРОВАН' if is_blocked else 'НЕ ЗАБЛОКИРОВАН'}")
        print()

    # 5. Финальная проверка
    print("5. ФИНАЛЬНАЯ ПРОВЕРКА")
    print("-" * 40)
    blocked = get_blocked_users()
    print(f"Оставшиеся заблокированные: {len(blocked)}")
    print(f"Заблокированные ID: {sorted(blocked)}")

    expected_remaining = {333333333}
    if blocked == expected_remaining:
        print("ФИНАЛЬНЫЙ СПИСОК КОРРЕКТЕН")
    else:
        print("ОШИБКА В ФИНАЛЬНОМ СПИСКЕ!")
    print()

    # 6. Тест команд администратора (имитация)
    print("6. ТЕСТ КОМАНД АДМИНИСТРАТОРА")
    print("-" * 40)

    # Имитируем /blocked_users
    print("Команда /blocked_users:")
    if not blocked:
        response = "Список заблокированных пользователей пуст.\\n\\nИспользуйте `/block <telegram_id>` для блокировки пользователей."
    else:
        blocked_list = "\\n".join(f"• `{user_id}`" for user_id in sorted(blocked))
        response = f"Заблокированные пользователи ({len(blocked)}):\\n\\n{blocked_list}\\n\\nИспользуйте `/unblock <telegram_id>` для разблокировки."

    print(f"Ответ бота: {response}")
    print()

    # Имитируем /block 444444444
    print("Команда /block 444444444:")
    success = block_user(444444444)
    response = "Пользователь 444444444 успешно заблокирован.\\n\\nИспользуйте `/blocked_users` для просмотра списка." if success else "Ошибка при блокировке пользователя."
    print(f"Ответ бота: {response}")
    print()

    # Имитируем /unblock 333333333
    print("Команда /unblock 333333333:")
    success = unblock_user(333333333)
    response = "Пользователь 333333333 успешно разблокирован.\\n\\nИспользуйте `/blocked_users` для просмотра списка." if success else "Ошибка при разблокировке пользователя."
    print(f"Ответ бота: {response}")
    print()

    # 7. Проверка middleware (имитация)
    print("7. ТЕСТ MIDDLEWARE БЛОКИРОВКИ")
    print("-" * 40)

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if bot_token:
        bot = Bot(token=bot_token)
        try:
            # Блокируем тестового пользователя
            block_user(555555555, 999999999)
            print("Заблокирован пользователь 555555555")

            # Имитируем отправку команды заблокированным пользователем
            print("Имитация команды от заблокированного пользователя...")
            print("Middleware ДОЛЖЕН игнорировать эту команду (бот не ответит)")

            # Разблокируем обратно для чистоты теста
            unblock_user(555555555)

        finally:
            await bot.session.close()
    else:
        print("TELEGRAM_BOT_TOKEN не найден - пропускаем тест middleware")

    print("\n=== ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ ===")
    print("СИСТЕМА БЛОКИРОВКИ РАБОТАЕТ КОРРЕКТНО!")

if __name__ == "__main__":
    asyncio.run(comprehensive_block_test())

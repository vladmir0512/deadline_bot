#!/usr/bin/env python3
"""
Тест ручной синхронизации дедлайнов.
"""

import asyncio
import sys
import os

# Добавляем текущую директорию в путь
sys.path.insert(0, '.')

from services import get_user_by_telegram_id
from sync_deadlines import sync_user_deadlines

async def main():
    # Получить пользователя по ID
    user = get_user_by_telegram_id(929644995)  # ID из сообщения
    if not user:
        print('Пользователь не найден')
        return

    print(f'Найден пользователь: {user.username}')

    # Синхронизировать дедлайны
    try:
        created, updated = await sync_user_deadlines(user)
        print(f'Синхронизация завершена: создано {created}, обновлено {updated}')
    except Exception as e:
        print(f'Ошибка синхронизации: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())

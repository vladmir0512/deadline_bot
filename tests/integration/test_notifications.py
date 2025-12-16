#!/usr/bin/env python3
"""
Тестирование отправки уведомлений.
"""

import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from bot import bot
from notifications import check_and_notify_deadlines

async def main():
    print("Тестирую отправку уведомлений...")
    stats = await check_and_notify_deadlines(bot)
    print("Результат проверки уведомлений:")
    print(f"  Пользователей уведомлено: {stats['users_notified']}")
    print(f"  Уведомлений отправлено: {stats['notifications_sent']}")

if __name__ == "__main__":
    asyncio.run(main())
"""
Тестовый скрипт для проверки синхронизации дедлайнов.
"""
import asyncio
from ...scripts.yonote_client import fetch_user_deadlines

async def test_sync():
    print("Тестируем получение дедлайнов для VJ_Games...")
    deadlines = await fetch_user_deadlines("VJ_Games")

    print(f"Найдено дедлайнов: {len(deadlines)}")
    for deadline in deadlines:
        print(f"  - {repr(deadline.title)} (users: {deadline.user_identifier})")

    print("\nТестируем получение всех дедлайнов...")
    all_deadlines = await fetch_user_deadlines(None)

    print(f"Всего дедлайнов: {len(all_deadlines)}")
    for deadline in all_deadlines[:5]:  # Показываем первые 5
        print(f"  - {repr(deadline.title)} (users: {deadline.user_identifier})")

if __name__ == "__main__":
    asyncio.run(test_sync())

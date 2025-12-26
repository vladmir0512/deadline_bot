"""
Ручная синхронизация дедлайнов для тестирования.
"""
import asyncio
from db import SessionLocal
from models import User
from scripts.sync_deadlines import sync_user_deadlines

async def manual_sync():
    session = SessionLocal()
    try:
        # Находим пользователя VJ_Games
        user = session.query(User).filter_by(username="VJ_Games").first()
        if not user:
            print("Пользователь VJ_Games не найден")
            return

        print(f"Синхронизируем дедлайны для пользователя {user.username} (ID: {user.id})")

        created, updated = await sync_user_deadlines(user)
        print(f"Результат: создано {created}, обновлено {updated}")

    finally:
        session.close()

if __name__ == "__main__":
    asyncio.run(manual_sync())

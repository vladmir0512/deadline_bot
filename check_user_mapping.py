"""
Скрипт для проверки соответствия пользователей и дедлайнов.
"""
from db import SessionLocal
from models import User, Deadline

def check_user_mapping():
    """Проверяем пользователей и их дедлайны"""
    session = SessionLocal()
    try:
        # Получаем всех пользователей
        users = session.query(User).all()
        print(f"Всего пользователей: {len(users)}")

        for user in users:
            print(f"\nПользователь ID {user.id}:")
            print(f"  Telegram ID: {user.telegram_id}")
            print(f"  Username: {repr(user.username)}")
            print(f"  Email: {repr(user.email)}")

            # Получаем дедлайны пользователя
            deadlines = session.query(Deadline).filter_by(user_id=user.id).all()
            print(f"  Дедлайнов: {len(deadlines)}")

            for deadline in deadlines[:3]:  # Показываем первые 3
                print(f"    - {repr(deadline.title)} (source: {deadline.source})")

            if len(deadlines) > 3:
                print(f"    ... и ещё {len(deadlines) - 3}")

    finally:
        session.close()

if __name__ == "__main__":
    check_user_mapping()

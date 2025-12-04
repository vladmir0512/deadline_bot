"""
Простой тест Этапа 2:
- создаём пользователя
- добавляем дедлайн и подписку
- читаем их обратно и печатаем в консоль

Запуск:
    python test_db.py
"""

from db import SessionLocal
from models import Deadline, Subscription, User, DeadlineStatus


def run_test() -> None:
    session = SessionLocal()
    try:
        # 1. создаём пользователя
        user = User(
            telegram_id=123456789,
            username="test_user",
            email="test@example.com",
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        # 2. создаём дедлайн
        deadline = Deadline(
            user_id=user.id,
            title="Тестовый дедлайн",
            description="Проверка работы моделей и БД",
            status=DeadlineStatus.ACTIVE,
            source="test",
        )
        session.add(deadline)

        # 3. создаём подписку
        subscription = Subscription(
            user_id=user.id,
            notification_type="telegram",
            active=True,
        )
        session.add(subscription)

        session.commit()

        # 4. читаем обратно из БД
        loaded_user = session.query(User).filter_by(id=user.id).first()
        loaded_deadlines = session.query(Deadline).filter_by(user_id=user.id).all()
        loaded_subscriptions = session.query(Subscription).filter_by(user_id=user.id).all()

        print("=== USER ===")
        print(f"id={loaded_user.id}, telegram_id={loaded_user.telegram_id}, username={loaded_user.username}, email={loaded_user.email}")

        print("=== DEADLINES ===")
        for d in loaded_deadlines:
            print(f"id={d.id}, title={d.title}, status={d.status}, source={d.source}")

        print("=== SUBSCRIPTIONS ===")
        for s in loaded_subscriptions:
            print(f"id={s.id}, type={s.notification_type}, active={s.active}")

    finally:
        session.close()


if __name__ == "__main__":
    run_test()



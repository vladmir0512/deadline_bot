#!/usr/bin/env python3
"""
Скрипт для проверки реальных дедлайнов в базе данных.
"""

from db import SessionLocal
from services import get_user_deadlines
from models import DeadlineStatus, User
from notifications import get_deadlines_at_halfway

def main():
    session = SessionLocal()
    try:
        # Получаем всех пользователей
        users = session.query(User).all()
        print(f"Найдено {len(users)} пользователей")

        all_deadlines = []
        for user in users:
            user_deadlines = get_user_deadlines(user.id, status=DeadlineStatus.ACTIVE, only_future=True)
            print(f"Пользователь {user.id} ({user.username}): {len(user_deadlines)} активных дедлайнов")
            all_deadlines.extend(user_deadlines)

        print(f"\nВсего активных дедлайнов: {len(all_deadlines)}")

        # Проверяем дедлайны на половине срока
        halfway_deadlines = get_deadlines_at_halfway(all_deadlines)
        print(f"Дедлайнов на половине срока: {len(halfway_deadlines)}")

        if halfway_deadlines:
            print("\nДедлайны на половине срока:")
            for deadline in halfway_deadlines:
                print(f"  {deadline.title}")
                print(f"    Создан: {deadline.created_at}")
                print(f"    Дедлайн: {deadline.due_date}")
                print(f"    Последнее уведомление: {deadline.last_notified_at}")
                print()

        print("\nВсе дедлайны:")
        for deadline in all_deadlines:
            from datetime import datetime, UTC
            now = datetime.now(UTC)
            created = deadline.created_at
            due = deadline.due_date

            if created and due:
                # Убеждаемся, что даты имеют timezone
                if created.tzinfo is None:
                    created = created.replace(tzinfo=UTC)
                if due.tzinfo is None:
                    due = due.replace(tzinfo=UTC)

                total_duration = due - created
                halfway_point = created + (total_duration / 2)
                time_diff_hours = (now - halfway_point).total_seconds() / 3600

                status = "На половине" if -0.5 <= time_diff_hours <= 3.0 else "Не на половине"
                print(f"  {deadline.title}: {status}")
                print(f"    Создан: {created}")
                print(f"    Дедлайн: {due}")
                print(f"    Разница от половины: {time_diff_hours:.2f} часов")
                print(f"    Половина: {halfway_point}")
                print(f"    Последнее уведомление: {deadline.last_notified_at}")
                print()

    finally:
        session.close()

if __name__ == "__main__":
    main()
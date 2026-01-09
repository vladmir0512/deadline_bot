#!/usr/bin/env python3
"""
Скрипт для тестирования уведомлений о половине срока с текущими дедлайнами.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from db import SessionLocal
from models import Deadline, DeadlineStatus, User
from notifications import get_deadlines_at_halfway
from datetime import datetime, UTC, timedelta

def main():
    session = SessionLocal()
    try:
        # Получаем пользователя
        user = session.query(User).filter_by(username="VJ_Games").first()
        if not user:
            print("Пользователь не найден, создаем...")
            user = User(telegram_id=929644995, username='VJ_Games')
            session.add(user)
            session.commit()
            session.refresh(user)

        # Получаем активные дедлайны
        from services import get_user_deadlines
        deadlines = get_user_deadlines(user.id, status=DeadlineStatus.ACTIVE, only_future=True)

        print(f"Найдено {len(deadlines)} активных дедлайнов")

        # Проверяем каждый дедлайн детально
        now = datetime.now(UTC)
        print(f"Текущее время: {now}")

        for deadline in deadlines:
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
                time_diff = (now - halfway_point).total_seconds()

                print(f"\nДедлайн: {deadline.title}")
                print(f"  Создан: {created}")
                print(f"  Дедлайн: {due}")
                print(f"  Половина: {halfway_point}")
                print(f"  Разница от половины: {time_diff/3600:.2f} часов")

                # Проверяем условия
                in_main_window = -1800 <= time_diff <= 10800  # От 30 мин до до 3 часов после
                past_halfway_no_notification = time_diff > 0 and not deadline.last_notified_at

                print(f"  В основном окне: {in_main_window} (-30 мин до +3 часов)")
                print(f"  Прошла половина без уведомления: {past_halfway_no_notification}")
                print(f"  Должен быть выбран: {in_main_window or past_halfway_no_notification}")
                print(f"  Последнее уведомление: {deadline.last_notified_at}")

        # Проверяем функцию
        halfway_deadlines = get_deadlines_at_halfway(deadlines)
        print(f"\nФункция get_deadlines_at_halfway нашла: {len(halfway_deadlines)}")
        for d in halfway_deadlines:
            print(f"  - {d.title}")

    finally:
        session.close()

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Создание тестового дедлайна, который находится точно на половине срока.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import SessionLocal
from models import Deadline, DeadlineStatus, User
from datetime import datetime, UTC, timedelta

def main():
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(username='VJ_Games').first()
        if not user:
            print("Пользователь не найден")
            return

        # Удаляем старые тестовые дедлайны
        session.query(Deadline).filter_by(user_id=user.id, source='test_manual').delete()
        session.commit()

        # Создаем дедлайн, который точно на половине срока
        now = datetime.now(UTC)
        created_at = now - timedelta(minutes=30)  # Создан 30 минут назад
        due_date = now + timedelta(minutes=30)    # Дедлайн через 30 минут

        halfway_point = created_at + (due_date - created_at) / 2  # Должен быть сейчас

        deadline = Deadline(
            user_id=user.id,
            title='Тест половины срока',
            description='Тестовый дедлайн для проверки уведомлений о половине срока',
            due_date=due_date,
            status=DeadlineStatus.ACTIVE,
            source='test_manual',
            created_at=created_at,
            updated_at=created_at,
            last_notified_at=None,
        )
        session.add(deadline)
        session.commit()
        session.refresh(deadline)

        print('Создан тестовый дедлайн:')
        print(f'  ID: {deadline.id}')
        print(f'  Создан: {created_at}')
        print(f'  Дедлайн: {due_date}')
        print(f'  Половина: {halfway_point}')
        print(f'  Сейчас: {now}')
        print('.1f')
        print('  Должен быть выбран для уведомления: ДА')

    finally:
        session.close()

if __name__ == "__main__":
    main()
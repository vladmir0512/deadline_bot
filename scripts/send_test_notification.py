#!/usr/bin/env python3
"""
Отправка тестового уведомления о дедлайне на половине срока.
"""

import asyncio
import os
from aiogram import Bot
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

from db import SessionLocal, init_db
from models import User
from notifications import send_deadline_notification

async def send_test_notification():
    """Отправить тестовое уведомление о дедлайне на половине срока."""

    # Устанавливаем правильный путь к БД
    import os
    os.environ['DATABASE_URL'] = 'sqlite:///C:/Users/vj/Documents/data/deadlines.db'

    # Инициализируем базу данных
    init_db()

    # Получаем токен бота
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("TELEGRAM_BOT_TOKEN не найден в переменных окружения")
        return

    bot = Bot(token=bot_token)

    session = SessionLocal()
    try:
        # Находим пользователя
        print("Ищу пользователя VJ_Games...")
        user = session.query(User).filter_by(username='VJ_Games').first()
        if not user:
            print("Пользователь VJ_Games не найден, пробую найти по telegram_id...")
            user = session.query(User).filter_by(telegram_id=929644995).first()
            if not user:
                print("Пользователь с telegram_id 929644995 не найден")
                # Попробуем найти всех пользователей
                all_users = session.query(User).all()
                print(f"Все пользователи в БД ({len(all_users)}):")
                for u in all_users:
                    print(f"  ID: {u.id}, Telegram: {u.telegram_id}, Username: {u.username}")
                return

        # Находим или создаем тестовый дедлайн
        from models import Deadline, DeadlineStatus
        from datetime import datetime, UTC, timedelta

        test_deadline = session.query(Deadline).filter_by(
            user_id=user.id,
            source='test_manual'
        ).first()

        if not test_deadline:
            print("Создаю тестовый дедлайн...")
            # Создаем дедлайн, который точно на половине срока
            now = datetime.now(UTC)
            created_at = now - timedelta(minutes=30)  # Создан 30 минут назад
            due_date = now + timedelta(minutes=30)    # Дедлайн через 30 минут

            test_deadline = Deadline(
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
            session.add(test_deadline)
            session.commit()
            session.refresh(test_deadline)
            print(f"Тестовый дедлайн создан: ID {test_deadline.id}")

        print(f"Отправляю тестовое уведомление пользователю {user.telegram_id}")
        print(f"   Дедлайн: {test_deadline.title}")
        print(f"   ID дедлайна: {test_deadline.id}")

        # Отправляем простое тестовое сообщение
        print("Отправляю простое сообщение...")
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text="🧪 *Тестовое уведомление о половине срока*\n\nДедлайн находится точно на половине срока выполнения!"
            )
            print("Сообщение отправлено успешно!")
            success = True
        except Exception as e:
            print(f"Ошибка при отправке: {e}")
            success = False

        if success:
            print("Уведомление отправлено успешно!")
        else:
            print("Не удалось отправить уведомление")

    finally:
        session.close()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(send_test_notification())
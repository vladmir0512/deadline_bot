"""
Скрипт для тестирования напоминания о дедлайне за половину срока.

Использование:
    python test_halfway_notification.py
"""

import os
import sys
from datetime import UTC, datetime, timedelta

from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

from db import SessionLocal, init_db
from models import Deadline, DeadlineStatus, Subscription, User
from notifications import get_deadlines_at_halfway, should_send_notification

# Настройка логирования
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_test_deadline(
    session,
    user: User,
    title: str,
    created_at: datetime,
    due_date: datetime,
) -> Deadline:
    """Создать тестовый дедлайн."""
    deadline = Deadline(
        user_id=user.id,
        title=title,
        description="Тестовый дедлайн для проверки напоминания за половину срока",
        due_date=due_date,
        status=DeadlineStatus.ACTIVE,
        source="test",
        created_at=created_at,
        updated_at=created_at,
        last_notified_at=None,
    )
    session.add(deadline)
    session.commit()
    session.refresh(deadline)
    return deadline


def test_halfway_calculation():
    """Тестировать вычисление половины срока."""
    print("=" * 80)
    print("ТЕСТ: Вычисление половины срока")
    print("=" * 80)

    session = SessionLocal()
    try:
        # Создаём тестового пользователя
        user = session.query(User).filter_by(telegram_id=999999999).first()
        if not user:
            user = User(
                telegram_id=999999999,
                username="test_user",
            )
            session.add(user)
            session.commit()
            session.refresh(user)

        # Удаляем старые тестовые дедлайны
        session.query(Deadline).filter_by(user_id=user.id, source="test").delete()
        session.commit()

        now = datetime.now(UTC)
        print(f"\nТекущее время: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")

        # Тест 1: Дедлайн, который уже прошёл половину срока
        print("\n" + "-" * 80)
        print("ТЕСТ 1: Дедлайн, который уже прошёл половину срока")
        print("-" * 80)
        created_at_1 = now - timedelta(days=10)  # Создан 10 дней назад
        due_date_1 = now + timedelta(days=10)  # Дедлайн через 10 дней
        halfway_1 = created_at_1 + (due_date_1 - created_at_1) / 2
        print(f"Создан: {created_at_1.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Дедлайн: {due_date_1.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Половина срока: {halfway_1.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Разница от половины: {(now - halfway_1).total_seconds() / 3600:.2f} часов")

        deadline_1 = create_test_deadline(session, user, "Тест 1: Прошла половина", created_at_1, due_date_1)
        halfway_deadlines_1 = get_deadlines_at_halfway([deadline_1])
        print(f"Найдено дедлайнов на половине срока: {len(halfway_deadlines_1)}")
        if halfway_deadlines_1:
            print("[OK] Дедлайн найден на половине срока")
        else:
            print("[FAIL] Дедлайн НЕ найден на половине срока")

        # Тест 2: Дедлайн, который ещё не дошёл до половины срока
        print("\n" + "-" * 80)
        print("ТЕСТ 2: Дедлайн, который ещё не дошёл до половины срока")
        print("-" * 80)
        created_at_2 = now - timedelta(days=2)  # Создан 2 дня назад
        due_date_2 = now + timedelta(days=18)  # Дедлайн через 18 дней
        halfway_2 = created_at_2 + (due_date_2 - created_at_2) / 2
        print(f"Создан: {created_at_2.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Дедлайн: {due_date_2.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Половина срока: {halfway_2.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Разница от половины: {(now - halfway_2).total_seconds() / 3600:.2f} часов")

        deadline_2 = create_test_deadline(session, user, "Тест 2: Ещё не половина", created_at_2, due_date_2)
        halfway_deadlines_2 = get_deadlines_at_halfway([deadline_2])
        print(f"Найдено дедлайнов на половине срока: {len(halfway_deadlines_2)}")
        if not halfway_deadlines_2:
            print("[OK] Дедлайн правильно НЕ найден (ещё не половина)")
        else:
            print("[FAIL] Дедлайн найден, хотя ещё не половина срока")

        # Тест 3: Дедлайн, который точно на половине срока (сейчас)
        print("\n" + "-" * 80)
        print("ТЕСТ 3: Дедлайн, который точно на половине срока (сейчас)")
        print("-" * 80)
        created_at_3 = now - timedelta(hours=2)  # Создан 2 часа назад
        due_date_3 = now + timedelta(hours=2)  # Дедлайн через 2 часа
        halfway_3 = created_at_3 + (due_date_3 - created_at_3) / 2
        print(f"Создан: {created_at_3.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Дедлайн: {due_date_3.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Половина срока: {halfway_3.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Разница от половины: {(now - halfway_3).total_seconds() / 60:.2f} минут")

        deadline_3 = create_test_deadline(session, user, "Тест 3: Сейчас половина", created_at_3, due_date_3)
        halfway_deadlines_3 = get_deadlines_at_halfway([deadline_3])
        print(f"Найдено дедлайнов на половине срока: {len(halfway_deadlines_3)}")
        if halfway_deadlines_3:
            print("[OK] Дедлайн найден на половине срока")
        else:
            print("[FAIL] Дедлайн НЕ найден на половине срока")

        # Тест 4: Дедлайн, который прошёл половину срока более 3 часов назад
        print("\n" + "-" * 80)
        print("ТЕСТ 4: Дедлайн, который прошёл половину срока более 3 часов назад")
        print("-" * 80)
        created_at_4 = now - timedelta(hours=10)  # Создан 10 часов назад
        due_date_4 = now + timedelta(hours=10)  # Дедлайн через 10 часов
        halfway_4 = created_at_4 + (due_date_4 - created_at_4) / 2
        print(f"Создан: {created_at_4.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Дедлайн: {due_date_4.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Половина срока: {halfway_4.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Разница от половины: {(now - halfway_4).total_seconds() / 3600:.2f} часов")

        deadline_4 = create_test_deadline(session, user, "Тест 4: Прошло >3 часа", created_at_4, due_date_4)
        halfway_deadlines_4 = get_deadlines_at_halfway([deadline_4])
        print(f"Найдено дедлайнов на половине срока: {len(halfway_deadlines_4)}")
        if not halfway_deadlines_4:
            print("[OK] Дедлайн правильно НЕ найден (прошло более 3 часов)")
        else:
            print("[FAIL] Дедлайн найден, хотя прошло более 3 часов")

        # Тест 5: Проверка should_send_notification
        print("\n" + "-" * 80)
        print("ТЕСТ 5: Проверка should_send_notification для типа 'halfway'")
        print("-" * 80)
        
        # Дедлайн без last_notified_at
        print(f"\nДедлайн без last_notified_at:")
        should_1 = should_send_notification(deadline_1, "halfway")
        print(f"  should_send_notification: {should_1}")
        if should_1:
            print("  [OK] Правильно: можно отправить (ещё не отправляли)")
        else:
            print("  [FAIL] Неправильно: должно быть True")

        # Дедлайн с last_notified_at менее 24 часов назад
        deadline_1.last_notified_at = now - timedelta(hours=12)
        session.add(deadline_1)
        session.commit()
        print(f"\nДедлайн с last_notified_at 12 часов назад:")
        should_2 = should_send_notification(deadline_1, "halfway")
        print(f"  should_send_notification: {should_2}")
        if not should_2:
            print("  [OK] Правильно: нельзя отправить (отправляли менее 24 часов назад)")
        else:
            print("  [FAIL] Неправильно: должно быть False")

        # Дедлайн с last_notified_at более 24 часов назад
        deadline_1.last_notified_at = now - timedelta(hours=25)
        session.add(deadline_1)
        session.commit()
        print(f"\nДедлайн с last_notified_at 25 часов назад:")
        should_3 = should_send_notification(deadline_1, "halfway")
        print(f"  should_send_notification: {should_3}")
        if should_3:
            print("  [OK] Правильно: можно отправить (прошло более 24 часов)")
        else:
            print("  [FAIL] Неправильно: должно быть True")

        # Итоговая сводка
        print("\n" + "=" * 80)
        print("ИТОГОВАЯ СВОДКА")
        print("=" * 80)
        all_deadlines = [deadline_1, deadline_2, deadline_3, deadline_4]
        all_halfway = get_deadlines_at_halfway(all_deadlines)
        print(f"\nВсего тестовых дедлайнов: {len(all_deadlines)}")
        print(f"Найдено на половине срока: {len(all_halfway)}")
        print("\nДетали:")
        for deadline in all_deadlines:
            is_halfway = deadline in all_halfway
            created = deadline.created_at
            due = deadline.due_date
            # Приводим даты к timezone-aware, чтобы избежать ошибок naive/aware
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            if due.tzinfo is None:
                due = due.replace(tzinfo=UTC)
            halfway = created + (due - created) / 2
            diff_hours = (now - halfway).total_seconds() / 3600
            status = "[OK] На половине" if is_halfway else "[ ] Не на половине"
            print(f"  {deadline.title}: {status} (разница: {diff_hours:.2f} часов)")

    finally:
        session.close()


if __name__ == "__main__":
    try:
        # Инициализируем БД если нужно
        init_db()
        test_halfway_calculation()
        print("\n[OK] Тестирование завершено успешно!")
    except Exception as e:
        logger.error(f"Ошибка при тестировании: {e}", exc_info=True)
        sys.exit(1)


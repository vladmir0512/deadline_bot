"""
Комплексная проверка работоспособности всех компонентов проекта.

Проверяет:
1. Инициализацию БД и модели данных
2. Работу с БД (CRUD операции)
3. Конфигурацию Yonote клиента
4. Базовую структуру проекта

Запуск:
    python verify_all.py
"""

import os
import sys
from datetime import UTC, datetime, timedelta

# Добавляем корневую директорию проекта в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import SessionLocal, init_db, engine
from models import Deadline, Subscription, User, DeadlineStatus, BlockedUser, UserNotificationSettings, DeadlineVerification


def check_database_connection() -> bool:
    """Проверка подключения к БД."""
    print("=" * 60)
    print("3. Проверка подключения к БД...")
    try:
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[OK] Подключение к БД успешно")
        return True
    except Exception as e:
        print(f"[ERROR] Ошибка подключения к БД: {e}")
        return False


def check_database_tables() -> bool:
    """Проверка наличия всех таблиц."""
    print("\n" + "=" * 60)
    print("4. Проверка таблиц БД...")
    try:
        from sqlalchemy import inspect

        inspector = inspect(engine)
        tables = inspector.get_table_names()
        required_tables = {"users", "deadlines", "subscriptions", "blocked_users", "user_notification_settings", "deadline_verifications"}

        missing = required_tables - set(tables)
        if missing:
            print(f"[ERROR] Отсутствуют таблицы: {missing}")
            print("  Попробуйте запустить: python init_db.py")
            return False

        print(f"[OK] Все таблицы на месте: {', '.join(required_tables)}")
        return True
    except Exception as e:
        print(f"[ERROR] Ошибка проверки таблиц: {e}")
        return False


def check_database_operations() -> bool:
    """Проверка CRUD операций с БД."""
    print("\n" + "=" * 60)
    print("5. Проверка операций с БД (CRUD)...")
    session = SessionLocal()
    try:
        # На всякий случай чистим старого тестового пользователя по telegram_id
        session.query(User).filter_by(telegram_id=999999999).delete()
        session.commit()

        # Создание пользователя
        test_user = User(
            telegram_id=999999999,
            username="verify_test_user",
            email="verify_test@example.com",
        )
        session.add(test_user)
        session.commit()
        session.refresh(test_user)
        print(f"[OK] Пользователь создан: id={test_user.id}, telegram_id={test_user.telegram_id}")

        # Создание дедлайна
        test_deadline = Deadline(
            user_id=test_user.id,
            title="Тестовый дедлайн для проверки",
            description="Проверка работы БД",
            due_date=datetime.now(UTC) + timedelta(days=7),
            status=DeadlineStatus.ACTIVE,
            source="verify_test",
        )
        session.add(test_deadline)
        session.commit()
        session.refresh(test_deadline)
        print(f"[OK] Дедлайн создан: id={test_deadline.id}, title={test_deadline.title}")

        # Создание подписки
        test_subscription = Subscription(
            user_id=test_user.id,
            notification_type="telegram",
            active=True,
        )
        session.add(test_subscription)
        session.commit()
        session.refresh(test_subscription)
        print(f"[OK] Подписка создана: id={test_subscription.id}, type={test_subscription.notification_type}")

        # Чтение данных
        loaded_user = session.query(User).filter_by(id=test_user.id).first()
        loaded_deadlines = session.query(Deadline).filter_by(user_id=test_user.id).all()
        loaded_subscriptions = session.query(Subscription).filter_by(user_id=test_user.id).all()

        assert loaded_user is not None, "Пользователь не найден"
        assert len(loaded_deadlines) > 0, "Дедлайны не найдены"
        assert len(loaded_subscriptions) > 0, "Подписки не найдены"

        print(f"[OK] Данные успешно прочитаны: {len(loaded_deadlines)} дедлайнов, {len(loaded_subscriptions)} подписок")

        # Обновление данных
        test_deadline.status = DeadlineStatus.COMPLETED
        session.commit()
        session.refresh(test_deadline)
        assert test_deadline.status == DeadlineStatus.COMPLETED, "Обновление не сработало"
        print("[OK] Обновление данных работает")

        # Удаление тестовых данных
        session.delete(test_deadline)
        session.delete(test_subscription)
        session.delete(test_user)
        session.commit()
        print("[OK] Тестовые данные удалены")

        return True
    except Exception as e:
        print(f"[ERROR] Ошибка операций с БД: {e}")
        import traceback

        traceback.print_exc()
        session.rollback()
        return False
    finally:
        session.close()


def check_models_structure() -> bool:
    """Проверка структуры моделей."""
    print("\n" + "=" * 60)
    print("6. Проверка структуры моделей...")
    try:
        # Проверка User
        assert hasattr(User, "telegram_id"), "User должен иметь поле telegram_id"
        assert hasattr(User, "username"), "User должен иметь поле username"
        assert hasattr(User, "email"), "User должен иметь поле email"
        assert hasattr(User, "deadlines"), "User должен иметь связь deadlines"
        assert hasattr(User, "subscriptions"), "User должен иметь связь subscriptions"
        assert hasattr(User, "notification_settings"), "User должен иметь связь notification_settings"
        assert hasattr(User, "deadline_verifications"), "User должен иметь связь deadline_verifications"
        print("[OK] Модель User корректна")

        # Проверка Deadline
        assert hasattr(Deadline, "user_id"), "Deadline должен иметь поле user_id"
        assert hasattr(Deadline, "title"), "Deadline должен иметь поле title"
        assert hasattr(Deadline, "due_date"), "Deadline должен иметь поле due_date"
        assert hasattr(Deadline, "status"), "Deadline должен иметь поле status"
        assert hasattr(Deadline, "source"), "Deadline должен иметь поле source"
        print("[OK] Модель Deadline корректна")

        # Проверка Subscription
        assert hasattr(Subscription, "user_id"), "Subscription должен иметь поле user_id"
        assert hasattr(Subscription, "notification_type"), "Subscription должен иметь поле notification_type"
        assert hasattr(Subscription, "active"), "Subscription должен иметь поле active"
        print("[OK] Модель Subscription корректна")

        # Проверка BlockedUser
        assert hasattr(BlockedUser, "telegram_id"), "BlockedUser должен иметь поле telegram_id"
        assert hasattr(BlockedUser, "blocked_by"), "BlockedUser должен иметь поле blocked_by"
        print("[OK] Модель BlockedUser корректна")

        # Проверка UserNotificationSettings
        assert hasattr(UserNotificationSettings, "user_id"), "UserNotificationSettings должен иметь поле user_id"
        assert hasattr(UserNotificationSettings, "notifications_enabled"), "UserNotificationSettings должен иметь поле notifications_enabled"
        print("[OK] Модель UserNotificationSettings корректна")

        # Проверка DeadlineVerification
        assert hasattr(DeadlineVerification, "deadline_id"), "DeadlineVerification должен иметь поле deadline_id"
        assert hasattr(DeadlineVerification, "user_id"), "DeadlineVerification должен иметь поле user_id"
        assert hasattr(DeadlineVerification, "status"), "DeadlineVerification должен иметь поле status"
        print("[OK] Модель DeadlineVerification корректна")

        # Проверка DeadlineStatus
        assert DeadlineStatus.ACTIVE == "active", "DeadlineStatus.ACTIVE должен быть 'active'"
        assert DeadlineStatus.COMPLETED == "completed", "DeadlineStatus.COMPLETED должен быть 'completed'"
        assert DeadlineStatus.CANCELED == "canceled", "DeadlineStatus.CANCELED должен быть 'canceled'"
        print("[OK] DeadlineStatus корректна")

        return True
    except Exception as e:
        print(f"[ERROR] Ошибка проверки моделей: {e}")
        return False


def check_yonote_client_config() -> bool:
    """Проверка конфигурации Yonote клиента."""
    print("\n" + "=" * 60)
    print("7. Проверка конфигурации Yonote клиента...")
    try:
        from scripts.yonote_client import fetch_user_deadlines

        # Проверка импорта
        print("[OK] Модуль yonote_client импортирован успешно")

        # Проверка переменных окружения
        api_key = os.getenv("YONOTE_API_KEY")
        base_url = os.getenv("YONOTE_BASE_URL", "https://unikeygroup.yonote.ru/api/v2")
        calendar_id = os.getenv("YONOTE_CALENDAR_ID")

        print(f"  YONOTE_BASE_URL: {base_url}")
        print(f"  YONOTE_API_KEY: {'задан' if api_key else 'не задан'}")
        print(f"  YONOTE_CALENDAR_ID: {'задан' if calendar_id else 'не задан'}")

        if not api_key:
            print("  ⚠ YONOTE_API_KEY не задан - тестирование API будет пропущено")
            return True  # Не критично для базовой проверки

        # Попытка вызвать функцию
        try:
            # Не асинхронно, просто проверка импорта
            print("[OK] Функция fetch_user_deadlines доступна")
        except Exception as e:
            print(f"  ⚠ Не удалось проверить fetch_user_deadlines: {e}")
            print("  (Это нормально, если API ключ неверный или не настроен)")
            return True  # Не критично

        return True
    except ImportError as e:
        print(f"[ERROR] Ошибка импорта yonote_client: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Ошибка проверки Yonote клиента: {e}")
        return False


def check_environment_variables() -> bool:
    """Проверка переменных окружения."""
    print("\n" + "=" * 60)
    print("2. Проверка переменных окружения...")
    try:
        from dotenv import load_dotenv

        # Ищем .env файл в директории выше
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_path = os.path.join(parent_dir, ".env")
        load_dotenv(env_path)

        # Проверка наличия .env файла
        if os.path.exists(env_path):
            print("[OK] Файл .env найден")
        else:
            print("[WARN] Файл .env не найден (можно создать вручную)")

        # Проверка важных переменных
        database_url = os.getenv("DATABASE_URL", "sqlite:///../deadlines.db")
        print(f"  DATABASE_URL: {database_url}")

        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        print(f"  TELEGRAM_BOT_TOKEN: {'задан' if telegram_token else 'не задан'}")

        yonote_api_key = os.getenv("YONOTE_API_KEY")
        print(f"  YONOTE_API_KEY: {'задан' if yonote_api_key else 'не задан'}")

        return True
    except Exception as e:
        print(f"[ERROR] Ошибка проверки переменных окружения: {e}")
        return False


def check_dependencies() -> bool:
    """Проверка установленных зависимостей."""
    print("\n" + "=" * 60)
    print("1. Проверка зависимостей...")
    try:
        import aiogram
        print(f"[OK] aiogram {aiogram.__version__}")

        import sqlalchemy
        print(f"[OK] SQLAlchemy {sqlalchemy.__version__}")

        import aiohttp
        print(f"[OK] aiohttp {aiohttp.__version__}")

        from dotenv import load_dotenv

        print("[OK] python-dotenv")

        return True
    except ImportError as e:
        print(f"✗ Отсутствует зависимость: {e}")
        print("  Запустите: pip install -r requirements.txt")
        return False


def main() -> None:
    """Главная функция проверки."""
    print("\n" + "=" * 60)
    print("ПРОВЕРКА РАБОТОСПОСОБНОСТИ ПРОЕКТА")
    print("=" * 60)

    results = []

    # Инициализация БД перед проверками
    try:
        init_db()
        print("[OK] База данных инициализирована")
    except Exception as e:
        print(f"[WARN] Предупреждение при инициализации БД: {e}")

    # Выполнение проверок
    results.append(("Зависимости", check_dependencies()))
    results.append(("Переменные окружения", check_environment_variables()))
    results.append(("Подключение к БД", check_database_connection()))
    results.append(("Таблицы БД", check_database_tables()))
    results.append(("Операции с БД", check_database_operations()))
    results.append(("Структура моделей", check_models_structure()))
    results.append(("Yonote клиент", check_yonote_client_config()))

    # Итоговый отчёт
    print("\n" + "=" * 60)
    print("ИТОГОВЫЙ ОТЧЁТ")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "[OK] ПРОЙДЕНО" if result else "[ERROR] ОШИБКА"
        print(f"{status}: {name}")

    print("\n" + "=" * 60)
    print(f"Результат: {passed}/{total} проверок пройдено")
    print("=" * 60)

    if passed == total:
        print("\n[OK] Все проверки пройдены успешно!")
        sys.exit(0)
    else:
        print("\n[WARN] Некоторые проверки не пройдены. Проверьте ошибки выше.")
        sys.exit(1)


if __name__ == "__main__":
    main()


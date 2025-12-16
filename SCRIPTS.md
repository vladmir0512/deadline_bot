# Как запускать проверки и утилиты

## Базовые проверки
- Интеграционные тесты: `pytest tests/integration` (если нужны отдельные файлы — запускай напрямую `python tests/integration/...`)
- Смоук всех компонентов: `python scripts/verify_all.py`

## Диагностика / check_*
- Сводка дедлайнов/источников: `python scripts/check_all_deadlines.py`, `python scripts/check_all_sources.py`, `python scripts/check_full_deadline_status.py`
- Проверка актуальности данных/половины срока: `python scripts/check_real_data.py`, `python tests/integration/test_halfway_notification.py`
- Состояние БД: `python scripts/check_db_state.py`, `python scripts/check_correct_user.py`, `python scripts/check_arahis_deadlines.py`

## Синхронизация
- Основной синк: `python scripts/sync_deadlines.py`
- Синк для VJ_Games/ArAhis: `python scripts/sync_arahis.py`

## Уведомления
- Тестовое уведомление (осторожно, реальный отправитель): `python scripts/send_test_notification.py`

## Генерация тестовых данных
- Дедлайн “на половине срока”: `python scripts/create_test_halfway_deadline.py`

## Отладка Yonote/CSV
- CSV-клиент: `python scripts/yonote_csv_client.py`
- Структура Yonote (raw/parsed): `python scripts/debug_yonote.py`
- `scripts/enhanced_debug.py` — требует рефактор под новую модель (сейчас выводит минимально, статус error в TEST_STATUS.md).

## Отладка БД
- `python scripts/debug_db.py` — ASCII-вывод; нужен рабочий `DATABASE_URL` (по умолчанию падает, если нет legacy БД с таблицами users/deadlines).

## Инициализация
- `python scripts/init_db.py` — создаёт таблицы, безопасен при повторном запуске.

## Примечания
- Все статусы и детали по каждому файлу см. в `TEST_STATUS.md`.
- Legacy миграции `migrate_add_*` удалены как неактуальные.


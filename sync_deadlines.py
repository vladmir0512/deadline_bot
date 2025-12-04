"""
Модуль синхронизации дедлайнов из Yonote в базу данных.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from db import SessionLocal
from models import Deadline, DeadlineStatus, User
from yonote_client import YonoteDeadline, fetch_user_deadlines

logger = logging.getLogger(__name__)


def sync_deadline_from_yonote(
    session: Session,
    user: User,
    yonote_deadline: YonoteDeadline,
) -> Deadline:
    """
    Синхронизировать один дедлайн из Yonote в БД.

    Args:
        session: Сессия БД
        user: Пользователь
        yonote_deadline: Дедлайн из Yonote

    Returns:
        Объект Deadline из БД
    """
    # Ищем существующий дедлайн по source и внешнему ID из Yonote
    # Используем source="yonote" и сохраняем ID из Yonote в source или создаём отдельное поле
    # Пока используем комбинацию source и title для поиска
    existing = (
        session.query(Deadline)
        .filter_by(
            user_id=user.id,
            source="yonote",
            title=yonote_deadline.title,
        )
        .first()
    )

    if existing:
        # Обновляем существующий дедлайн
        existing.description = yonote_deadline.description
        existing.due_date = yonote_deadline.due_date
        existing.updated_at = datetime.now(UTC)
        # Если дедлайн был отменён в Yonote, можно обновить статус
        # Пока оставляем статус как есть
        return existing

    # Создаём новый дедлайн
    deadline = Deadline(
        user_id=user.id,
        title=yonote_deadline.title,
        description=yonote_deadline.description,
        due_date=yonote_deadline.due_date,
        status=DeadlineStatus.ACTIVE,
        source="yonote",
    )
    session.add(deadline)
    return deadline


async def sync_user_deadlines(user: User) -> tuple[int, int]:
    """
    Синхронизировать дедлайны для одного пользователя.

    Args:
        user: Пользователь

    Returns:
        Кортеж (количество созданных, количество обновлённых)
    """
    session = SessionLocal()
    created_count = 0
    updated_count = 0

    try:
        # Проверяем, что пользователь зарегистрировал ник для Yonote
        if not user.username:
            logger.warning(f"Пользователь {user.id} не зарегистрировал ник для синхронизации. Синхронизация не выполнена.")
            return 0, 0

        # Определяем идентификатор пользователя для фильтрации в Yonote
        user_identifier = user.username
        logger.info(f"Синхронизация для пользователя {user.id} по нику: {user.username}")

        # Получаем дедлайны из Yonote
        try:
            logger.info(f"Запрос дедлайнов из Yonote для идентификатора: {user_identifier or 'все'}")
            yonote_deadlines = await fetch_user_deadlines(user_identifier)
            logger.info(f"Получено {len(yonote_deadlines)} дедлайнов из Yonote для пользователя {user.id}")
        except Exception as e:
            logger.error(f"Ошибка при получении дедлайнов из Yonote для пользователя {user.id}: {e}", exc_info=True)
            return 0, 0

        # Если дедлайнов нет, но user_identifier задан, возможно фильтрация слишком строгая
        if not yonote_deadlines and user_identifier:
            logger.warning(
                f"Не найдено дедлайнов для идентификатора '{user_identifier}'. "
                "Попробую синхронизировать все дедлайны и привязать по совпадению."
            )
            # Пробуем получить все дедлайны
            try:
                all_deadlines = await fetch_user_deadlines(None)
                logger.info(f"Получено {len(all_deadlines)} дедлайнов без фильтрации")

                # Фильтруем вручную - проверяем, содержит ли дедлайн пользователя
                # Сначала проверяем по email
                yonote_deadlines = [
                    d for d in all_deadlines
                    if d.user_identifier and user_identifier.lower() in d.user_identifier.lower()
                ]

                # Если по email не нашли, пробуем по username
                if not yonote_deadlines and user and user.username:
                    yonote_deadlines = [
                        d for d in all_deadlines
                        if d.user_identifier and user.username.lower() in d.user_identifier.lower()
                    ]
                    if yonote_deadlines:
                        logger.info(f"Найдено {len(yonote_deadlines)} дедлайнов по username: {user.username}")

                logger.info(f"После фильтрации осталось {len(yonote_deadlines)} дедлайнов")
            except Exception as e:
                logger.error(f"Ошибка при получении всех дедлайнов: {e}")

        # Получаем все существующие дедлайны пользователя из базы, связанные с Yonote
        existing_db_deadlines = session.query(Deadline).filter_by(
            user_id=user.id,
            source="yonote"
        ).all()

        # Создаем множество заголовков дедлайнов из Yonote для быстрого поиска
        yonote_titles = {dl.title for dl in yonote_deadlines}

        # Удаляем дедлайны, которых больше нет в Yonote
        deleted_count = 0
        for existing_dl in existing_db_deadlines:
            if existing_dl.title not in yonote_titles:
                logger.info(f"Удаляем дедлайн '{existing_dl.title}' - больше не назначен пользователю в Yonote")
                session.delete(existing_dl)
                deleted_count += 1

        # Синхронизируем каждый дедлайн
        for yonote_deadline in yonote_deadlines:
            existing = (
                session.query(Deadline)
                .filter_by(
                    user_id=user.id,
                    source="yonote",
                    title=yonote_deadline.title,
                )
                .first()
            )

            if existing:
                # Обновляем существующий
                existing.description = yonote_deadline.description
                existing.due_date = yonote_deadline.due_date
                existing.updated_at = datetime.now(UTC)
                updated_count += 1
            else:
                # Создаём новый
                deadline = Deadline(
                    user_id=user.id,
                    title=yonote_deadline.title,
                    description=yonote_deadline.description,
                    due_date=yonote_deadline.due_date,
                    status=DeadlineStatus.ACTIVE,
                    source="yonote",
                )
                session.add(deadline)
                created_count += 1

        session.commit()

        if deleted_count > 0:
            logger.info(f"Удалено {deleted_count} дедлайнов, которые больше не назначены пользователю")
        logger.info(
            f"Синхронизировано дедлайнов для пользователя {user.id}: "
            f"создано {created_count}, обновлено {updated_count}"
        )

        return created_count, updated_count

    except Exception as e:
        logger.error(f"Ошибка при синхронизации дедлайнов для пользователя {user.id}: {e}", exc_info=True)
        session.rollback()
        return 0, 0
    finally:
        session.close()


async def sync_all_deadlines() -> dict[str, int]:
    """
    Синхронизировать дедлайны для всех пользователей.

    Returns:
        Словарь со статистикой: {"total_users": ..., "created": ..., "updated": ...}
    """
    session = SessionLocal()
    try:
        users = session.query(User).all()
        total_created = 0
        total_updated = 0

        for user in users:
            # Пропускаем пользователей, которые не зарегистрировали ник
            if not user.username:
                logger.info(f"Пользователь {user.id} не имеет зарегистрированного ника. Пропускаем синхронизацию.")
                continue

            created, updated = await sync_user_deadlines(user)
            total_created += created
            total_updated += updated

        logger.info(
            f"Синхронизация завершена: пользователей {len(users)}, "
            f"создано дедлайнов {total_created}, обновлено {total_updated}"
        )

        return {
            "total_users": len(users),
            "created": total_created,
            "updated": total_updated,
        }
    finally:
        session.close()


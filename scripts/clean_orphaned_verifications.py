#!/usr/bin/env python3
"""
Скрипт для очистки сиротских запросов на проверку дедлайнов.

Удаляет DeadlineVerification, у которых deadline_id указывает на несуществующий дедлайн.
"""

import logging
import os
import sys

# Добавляем корневую директорию проекта в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import exists
from db import SessionLocal
from models import DeadlineVerification, Deadline

logger = logging.getLogger(__name__)


def clean_orphaned_verifications() -> int:
    """
    Очистить сиротские запросы на проверку.

    Returns:
        Количество удаленных записей
    """
    session = SessionLocal()
    try:
        # Находим все verification, у которых deadline_id не существует в таблице deadlines
        orphaned_verifications = (
            session.query(DeadlineVerification)
            .outerjoin(Deadline, DeadlineVerification.deadline_id == Deadline.id)
            .filter(Deadline.id.is_(None))
            .all()
        )

        count = len(orphaned_verifications)
        if count > 0:
            for verification in orphaned_verifications:
                logger.info(f"Удаляем сиротскую verification ID={verification.id}, deadline_id={verification.deadline_id}")
                session.delete(verification)

            session.commit()
            logger.info(f"Удалено {count} сиротских verification")
        else:
            logger.info("Сиротских verification не найдено")

        return count
    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка при очистке сиротских verification: {e}", exc_info=True)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    clean_orphaned_verifications()
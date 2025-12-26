import asyncio
import sys
sys.path.append('scripts')
from yonote_client import fetch_user_deadlines

async def debug_save():
    print('Получаем данные из API...')
    deadlines = await fetch_user_deadlines('VJ_Games')

    print(f'Получено {len(deadlines)} дедлайнов')
    for i, d in enumerate(deadlines[:2], 1):
        print(f'{i}. Title: {repr(d.title)}')
        print(f'   Type: {type(d.title)}')
        print(f'   UTF-8 bytes: {d.title.encode("utf-8")}')

        # Попробуем сохранить в базу
        from db import init_db, SessionLocal
        from models import Deadline

        init_db()
        session = SessionLocal()
        try:
            # Создаем новый дедлайн для теста
            test_dl = Deadline(
                user_id=1,
                title=d.title,
                description=d.description,
                due_date=d.due_date,
                status='active',
                source='yonote_test',
                source_id=f'test_{i}',
                created_at=None,
                updated_at=None,
            )
            session.add(test_dl)
            session.commit()

            # Прочитаем обратно
            saved = session.query(Deadline).filter_by(source_id=f'test_{i}').first()
            if saved:
                print(f'   Saved title: {repr(saved.title)}')
                print(f'   Saved UTF-8: {saved.title.encode("utf-8")}')

            # Удалим тестовую запись
            session.delete(saved)
            session.commit()

        finally:
            session.close()

if __name__ == "__main__":
    asyncio.run(debug_save())

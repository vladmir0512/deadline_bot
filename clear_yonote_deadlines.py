from db import init_db, SessionLocal
from models import Deadline

init_db()
session = SessionLocal()
try:
    # Удаляем все существующие Yonote дедлайны
    deleted = session.query(Deadline).filter_by(source='yonote').delete()
    session.commit()
    print(f'Удалено {deleted} дедлайнов Yonote из базы данных')

    # Проверяем, что база пуста
    remaining = session.query(Deadline).filter_by(source='yonote').count()
    print(f'Осталось {remaining} дедлайнов Yonote')

finally:
    session.close()

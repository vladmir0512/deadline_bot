from db import init_db, SessionLocal
from models import Deadline

init_db()
session = SessionLocal()
try:
    deadlines = session.query(Deadline).filter_by(source='yonote').limit(3).all()
    print('Данные через SQLAlchemy:')
    for dl in deadlines:
        print(f'ID: {dl.id}, Title: {repr(dl.title)}')
        print(f'  Type: {type(dl.title)}')
        print(f'  Length: {len(dl.title) if dl.title else 0}')
        if dl.title:
            print(f'  UTF-8 bytes: {dl.title.encode("utf-8")}')
finally:
    session.close()

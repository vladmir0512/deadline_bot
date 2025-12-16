import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import SessionLocal
from models import Deadline

# Проверим базу данных для пользователя с telegram_id 929644995 (ID 4 - mirialliya)
session = SessionLocal()
try:
    deadlines = session.query(Deadline).filter_by(user_id=4).all()
    print(f'Пользователь mirialliya (ID 4, telegram_id 929644995) теперь имеет {len(deadlines)} дедлайнов в базе:')
    for dl in deadlines:
        print(f'  - {dl.title} (Due: {dl.due_date})')
finally:
    session.close()

print()

# Теперь проверим через сервис
from services import get_user_deadlines, get_user_by_telegram_id
from models import DeadlineStatus
user = get_user_by_telegram_id(929644995)  # ваш telegram ID
print(f'Информация о пользователе: ID={user.id}, username={user.username}, email={user.email}')

user_deadlines = get_user_deadlines(user.id, status=DeadlineStatus.ACTIVE)
print(f'Через сервис пользователь mirialliya (ID {user.id}) имеет {len(user_deadlines)} активных дедлайнов:')
for dl in user_deadlines:
    print(f'  - {dl.title} (Due: {dl.due_date})')
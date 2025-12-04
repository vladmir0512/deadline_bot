from db import SessionLocal
from models import Deadline

# Проверим базу данных для пользователя VJ_Games (ID 2)
session = SessionLocal()
try:
    deadlines = session.query(Deadline).filter_by(user_id=2).all()
    print(f'Пользователь VJ_Games (ID 2) теперь имеет {len(deadlines)} дедлайнов в базе:')
    for dl in deadlines:
        print(f'  - {dl.title} (Due: {dl.due_date})')
finally:
    session.close()

print()

# Теперь проверим через сервис
from services import get_user_deadlines
from models import DeadlineStatus
user_deadlines = get_user_deadlines(2, status=DeadlineStatus.ACTIVE)
print(f'Через сервис пользователь VJ_Games (ID 2) имеет {len(user_deadlines)} активных дедлайнов:')
for dl in user_deadlines:
    print(f'  - {dl.title} (Due: {dl.due_date})')
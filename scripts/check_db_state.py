import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import get_user_by_telegram_id, get_user_deadlines
from models import DeadlineStatus

user = get_user_by_telegram_id(929644995)  # ваш telegram ID
print(f'User: ID={user.id}, username={user.username}')

deadlines = get_user_deadlines(user.id, status=DeadlineStatus.ACTIVE)
print(f'Active deadlines in DB: {len(deadlines)}')
for i, dl in enumerate(deadlines, 1):
    print(f'  {i}. {dl.title} (Due: {dl.due_date}, ID: {dl.id})')

# Check all deadlines regardless of status
from models import Deadline
from db import SessionLocal

session = SessionLocal()
try:
    all_user_deadlines = session.query(Deadline).filter_by(user_id=user.id).all()
    print(f'Total deadlines in DB (any status): {len(all_user_deadlines)}')
    for i, dl in enumerate(all_user_deadlines, 1):
        print(f'  {i}. {dl.title} (Due: {dl.due_date}, ID: {dl.id}, Status: {dl.status})')
finally:
    session.close()
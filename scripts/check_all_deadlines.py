import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import SessionLocal
from models import Deadline, User
from services import get_user_by_telegram_id

# Check for all deadlines for the user to see if any duplicates exist
user = get_user_by_telegram_id(929644995)
print(f'Checking all deadlines for user {user.username} (ID: {user.id})')

session = SessionLocal()
try:
    # Get all deadlines for the user regardless of source
    all_user_deadlines = session.query(Deadline).filter_by(user_id=user.id).order_by(Deadline.id).all()
    print(f'Found {len(all_user_deadlines)} total deadlines:')
    for i, dl in enumerate(all_user_deadlines):
        print(f'  {i+1}. ID:{dl.id} - {dl.title} (Due: {dl.due_date}, Source: {dl.source}, Status: {dl.status})')

    # Also get ALL deadlines from the database for context
    all_deadlines = session.query(Deadline).all()
    print(f'\nIn total database, there are {len(all_deadlines)} deadlines for ALL users:')
    for user_check in [1, 2, 3, 4]:  # Check specific user IDs
        user_deadlines = session.query(Deadline).filter_by(user_id=user_check).all()
        print(f'  User {user_check}: {len(user_deadlines)} deadlines')
        for dl in user_deadlines:
            print(f'    - {dl.title} [{dl.source}]')
finally:
    session.close()
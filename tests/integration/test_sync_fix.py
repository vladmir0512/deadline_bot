import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services import get_user_by_telegram_id
from scripts.sync_deadlines import sync_user_deadlines
import asyncio

# Get user by telegram ID
user = get_user_by_telegram_id(929644995)  # your telegram ID
print(f'Syncing for user: ID={user.id}, username={user.username}')

if user:
    created, updated = asyncio.run(sync_user_deadlines(user))
    print(f'Sync completed: created {created}, updated {updated}')
    
    # Check the user's deadlines after sync
    from services import get_user_deadlines
    from models import DeadlineStatus
    deadlines = get_user_deadlines(user.id, status=DeadlineStatus.ACTIVE)
    print(f'After sync, user {user.username} (ID {user.id}) has {len(deadlines)} active deadlines:')
    for dl in deadlines:
        print(f'  - {dl.title} (Due: {dl.due_date}, ID: {dl.id})')
        
    # Also check all deadlines regardless of status
    from models import Deadline
    from db import SessionLocal
    session = SessionLocal()
    try:
        all_user_deadlines = session.query(Deadline).filter_by(user_id=user.id).all()
        print(f'Total deadlines in DB (any status): {len(all_user_deadlines)}')
        for dl in all_user_deadlines:
            print(f'  - {dl.title} (Due: {dl.due_date}, ID: {dl.id}, Status: {dl.status})')
    finally:
        session.close()
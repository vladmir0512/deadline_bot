import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import SessionLocal
from models import Deadline, DeadlineStatus, User
from datetime import datetime
from zoneinfo import ZoneInfo

# First, let's manually insert an extra deadline that doesn't exist in the current CSV
# This simulates the issue - a deadline that's in database but not in Yonote anymore
session = SessionLocal()
try:
    # Create an extra deadline that should be deleted by sync
    extra_deadline = Deadline(
        user_id=4,  # VJ_Games user ID
        title="Extra Test Deadline That Should Be Deleted",
        description="This is a test deadline that doesn't exist in Yonote CSV",
        due_date=datetime.now(ZoneInfo("UTC")).replace(year=2025, month=12, day=15),  # Future date
        status=DeadlineStatus.ACTIVE,
        source="yonote",  # Mark as from yonote so it gets affected by sync
    )
    
    session.add(extra_deadline)
    session.commit()
    
    print(f"Added extra deadline with ID {extra_deadline.id}")
    
    # Now check how many deadlines there are now
    user_deadlines_after_insert = session.query(Deadline).filter_by(user_id=4, source="yonote").all()
    print(f"Now database has {len(user_deadlines_after_insert)} Yonote deadlines:")
    for dl in user_deadlines_after_insert:
        print(f"  - ID:{dl.id} {dl.title}")
    
finally:
    session.close()

print("Now let's run sync to see if it removes the extra deadline...")

# Run sync
from services import get_user_by_telegram_id, get_or_create_user
from scripts.sync_deadlines import sync_user_deadlines
import asyncio

user = get_user_by_telegram_id(929644995)
if not user:
    # Create user if not exists
    user = get_or_create_user(929644995, 'VJ_Games')
    # Set username if not set
    session_update = SessionLocal()
    try:
        session_update.query(User).filter_by(telegram_id=929644995).update({'username': 'VJ_Games'})
        session_update.commit()
        session_update.refresh(user)
    finally:
        session_update.close()

print(f'Syncing for user: {user.username} (ID: {user.id})')

if user:
    created, updated = asyncio.run(sync_user_deadlines(user))
    print(f'Sync completed: created {created}, updated {updated}')
    
    # Check the user's deadlines after sync
    from services import get_user_deadlines
    deadlines = get_user_deadlines(user.id, status=DeadlineStatus.ACTIVE, only_future=True, include_no_date=True)
    print(f'After sync, user has {len(deadlines)} active deadlines:')
    for dl in deadlines:
        print(f'  - {dl.title} (Due: {dl.due_date}, ID: {dl.id})')
        
    # Also check all deadlines in DB (to see if extra was removed)
    session = SessionLocal()
    try:
        all_user_deadlines = session.query(Deadline).filter_by(user_id=4, source="yonote").all()
        print(f'Total Yonote deadlines in DB after sync: {len(all_user_deadlines)}')
        for dl in all_user_deadlines:
            print(f'  - ID:{dl.id} {dl.title}')
    finally:
        session.close()
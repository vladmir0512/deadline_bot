from db import SessionLocal
from models import Deadline, DeadlineStatus
from datetime import datetime
from zoneinfo import ZoneInfo

# Manually add 2 EXTRA deadlines to simulate the situation where 
# the database has more deadlines than Yonote CSV
session = SessionLocal()
try:
    # Create first extra deadline that doesn't exist in current Yonote CSV
    extra_deadline1 = Deadline(
        user_id=4,  # VJ_Games user ID
        title="Extra Deadline 1 That Should Be Deleted After Sync",
        description="This deadline does not exist in the current Yonote CSV",
        due_date=datetime.now(ZoneInfo("UTC")).replace(year=2025, month=12, day=15),
        status=DeadlineStatus.ACTIVE,
        source="yonote",  # Mark as from yonote so it gets affected by sync
    )
    
    extra_deadline2 = Deadline(
        user_id=4,  # VJ_Games user ID
        title="Extra Deadline 2 That Should Be Deleted After Sync", 
        description="This deadline also does not exist in the current Yonote CSV",
        due_date=datetime.now(ZoneInfo("UTC")).replace(year=2025, month=12, day=16),
        status=DeadlineStatus.ACTIVE,
        source="yonote",  # Mark as from yonote so it gets affected by sync
    )
    
    session.add(extra_deadline1)
    session.add(extra_deadline2)
    session.commit()
    
    print(f"Added 2 extra deadlines. Now database has {session.query(Deadline).filter_by(user_id=4, source='yonote').count()} Yonote deadlines")
    
    # Check current state
    current_deadlines = session.query(Deadline).filter_by(user_id=4, source="yonote").all()
    print(f"Current deadlines in database:")
    for dl in current_deadlines:
        print(f"  - ID:{dl.id} {dl.title}")
    
finally:
    session.close()

print()
print("Now running sync to see if deletion works correctly...")
print()

# Now run sync to see if it removes the 2 extra deadlines
from services import get_user_by_telegram_id
from sync_deadlines import sync_user_deadlines
import asyncio

user = get_user_by_telegram_id(929644995)
print(f'Syncing for user: {user.username} (ID: {user.id})')

if user:
    created, updated = asyncio.run(sync_user_deadlines(user))
    print(f'Sync completed: created {created}, updated {updated}')
    
    # Check the database after sync
    session = SessionLocal()
    try:
        final_deadlines = session.query(Deadline).filter_by(user_id=4, source="yonote").all()
        print(f'After sync, database has {len(final_deadlines)} Yonote deadlines:')
        for dl in final_deadlines:
            print(f'  - ID:{dl.id} {dl.title}')
            
        # Also check via the get_user_deadlines function (what /mydeadlines uses)
        from services import get_user_deadlines
        my_deadlines = get_user_deadlines(user.id, status="active", only_future=True, include_no_date=True)
        print(f'MyDeadlines function returns {len(my_deadlines)} deadlines:')
        for dl in my_deadlines:
            print(f'  - {dl.title} (Due: {dl.due_date})')
            
    finally:
        session.close()
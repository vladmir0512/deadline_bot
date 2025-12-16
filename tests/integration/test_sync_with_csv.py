import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services import get_user_by_telegram_id
from scripts.sync_deadlines import sync_user_deadlines
import asyncio

# Get user by telegram ID (yours is 929644995 based on the database)
user = get_user_by_telegram_id(929644995)  # VJ_Games
print(f'User: {user.username}, email: {user.email}')

if user:
    created, updated = asyncio.run(sync_user_deadlines(user))
    print(f'Sync completed: created {created}, updated {updated}')
    
    # Now check the user's deadlines
    from services import get_user_deadlines
    from models import DeadlineStatus
    deadlines = get_user_deadlines(user.id, status=DeadlineStatus.ACTIVE)
    print(f'User now has {len(deadlines)} deadlines:')
    for dl in deadlines:
        print(f'  - {dl.title} (Due: {dl.due_date})')
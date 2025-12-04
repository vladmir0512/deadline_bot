# Final verification that sync works correctly
from services import get_user_by_telegram_id
from sync_deadlines import sync_user_deadlines
from services import get_user_deadlines
from models import DeadlineStatus
import asyncio

user = get_user_by_telegram_id(929644995)
print(f'Verifying sync for user: {user.username} (ID: {user.id})')

# First, check how many deadlines the user currently has
current_deadlines = get_user_deadlines(user.id, status=DeadlineStatus.ACTIVE)
print(f'Before sync, user has {len(current_deadlines)} active deadlines')

# Perform sync
created, updated = asyncio.run(sync_user_deadlines(user))
print(f'Sync completed: created {created}, updated {updated}')

# Check deadlines after sync
after_sync_deadlines = get_user_deadlines(user.id, status=DeadlineStatus.ACTIVE)
print(f'After sync, user has {len(after_sync_deadlines)} active deadlines')

# Validate that the counts match the CSV data
from yonote_client import YonoteClient
async def get_csv_count():
    client = YonoteClient()
    all_deadlines = await client.fetch_deadlines_raw()
    user_csv_deadlines = [
        dl for dl in all_deadlines 
        if dl.user_identifier and 'vj_games' in dl.user_identifier.lower()
    ]
    return len(user_csv_deadlines), [dl.title for dl in user_csv_deadlines]

csv_count, csv_titles = asyncio.run(get_csv_count())
print(f'CSV data shows {csv_count} deadlines for user, with titles: {csv_titles}')
print(f'Database now has {len(after_sync_deadlines)} deadlines with titles: {[dl.title for dl in after_sync_deadlines]}')

if len(after_sync_deadlines) == csv_count:
    print('✅ SUCCESS: Database and CSV counts match perfectly!')
else:
    print('❌ ERROR: Counts do not match')
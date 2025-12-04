from services import get_user_by_telegram_id
from sync_deadlines import sync_user_deadlines

# Get user by telegram ID (yours is likely 929644995 based on the database)
user = get_user_by_telegram_id(929644995)  # VJ_Games
print(f'Found user: {user.username}, email: {user.email}')

if user:
    import asyncio
    created, updated = asyncio.run(sync_user_deadlines(user))
    print(f'Sync completed: created {created}, updated {updated}')
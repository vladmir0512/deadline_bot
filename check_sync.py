from services import get_user_by_telegram_id
from sync_deadlines import sync_user_deadlines
import asyncio

# Get user by telegram ID (yours is 929644995 based on the database)
user = get_user_by_telegram_id(929644995)  # VJ_Games
print(f'User: {user.username}, email: {user.email}')

if user:
    created, updated = asyncio.run(sync_user_deadlines(user))
    print(f'Sync again completed: created {created}, updated {updated}')
    
    from db import SessionLocal
    session = SessionLocal()
    try:
        from models import Deadline
        user_deadlines = session.query(Deadline).filter_by(user_id=user.id).all()
        print(f'Now user has {len(user_deadlines)} deadlines in DB:')
        for dl in user_deadlines:
            print(f'  - {dl.title} (Due: {dl.due_date})')
    finally:
        session.close()
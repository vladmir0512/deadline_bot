import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import SessionLocal
from models import Deadline
from services import get_user_by_telegram_id

# Check all deadlines for user regardless of source
user = get_user_by_telegram_id(929644995)
print(f'Getting ALL deadlines for user {user.username} (ID: {user.id}) - regardless of source:')

session = SessionLocal()
try:
    all_user_all_sources = session.query(Deadline).filter_by(user_id=user.id).all()
    print(f'Found {len(all_user_all_sources)} total deadlines from ALL sources:')
    for i, dl in enumerate(all_user_all_sources):
        print(f'  {i+1}. ID:{dl.id}, Title:"{dl.title}", Source:"{dl.source}", Status:"{dl.status}"')
        
    print()
    
    # Count by source
    from collections import Counter
    sources = Counter(dl.source for dl in all_user_all_sources)
    print('Breakdown by source:')
    for source, count in sources.items():
        print(f'  {source}: {count} deadlines')
        
finally:
    session.close()

# Also run the original sync again to see log in detail
from sync_deadlines import sync_user_deadlines
import asyncio

print()
print('Running sync for detailed logs...')
result = asyncio.run(sync_user_deadlines(user))
print(f'Sync result: {result}')
import asyncio
from yonote_client import fetch_user_deadlines

# Test fetching deadlines for different identifiers
print('Testing fetch_user_deadlines with email:')
deadlines_email = asyncio.run(fetch_user_deadlines('vjgamer2001@gmail.com'))
print(f'Found {len(deadlines_email)} deadlines for email')

print('\nTesting fetch_user_deadlines with username:')
deadlines_username = asyncio.run(fetch_user_deadlines('VJ_Games'))
print(f'Found {len(deadlines_username)} deadlines for username')

print('\nTesting fetch_user_deadlines with no filter:')
deadlines_all = asyncio.run(fetch_user_deadlines(None))
print(f'Found {len(deadlines_all)} total deadlines')

print('\nChecking all deadlines that contain VJ_Games:')
for dl in deadlines_all:
    if dl.user_identifier and 'VJ_Games' in dl.user_identifier:
        print(f'  - {dl.title} (Due: {dl.due_date}, People: {dl.user_identifier})')
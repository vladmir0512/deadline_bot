import asyncio
from scripts.yonote_client import fetch_user_deadlines

# Test fetching deadlines for the exact username
print('Testing fetch_user_deadlines with username ArAhis:')
try:
    deadlines_username = asyncio.run(fetch_user_deadlines('ArAhis'))
    print(f'Found {len(deadlines_username)} deadlines for username ArAhis')
except Exception as e:
    print(f'Error fetching deadlines: {e}')

print('\nTesting fetch_user_deadlines with lowercase arahis:')
try:
    deadlines_lower = asyncio.run(fetch_user_deadlines('arahis'))
    print(f'Found {len(deadlines_lower)} deadlines for username arahis')
except Exception as e:
    print(f'Error fetching deadlines: {e}')

print('\nTesting fetch_user_deadlines with no filter:')
try:
    deadlines_all = asyncio.run(fetch_user_deadlines(None))
    print(f'Found {len(deadlines_all)} total deadlines')
except Exception as e:
    print(f'Error fetching deadlines: {e}')

print('\nChecking all deadlines that contain ArAhis:')
for dl in deadlines_all:
    if dl.user_identifier and ('ArAhis' in dl.user_identifier or 'arahis' in dl.user_identifier.lower()):
        print(f'  - {dl.title} (Due: {dl.due_date}, People: {dl.user_identifier})')
import asyncio
from scripts.yonote_client import fetch_user_deadlines

async def test_csv():
    print('Testing fetch_user_deadlines with username ArAhis:')
    deadlines_username = await fetch_user_deadlines('ArAhis')
    print(f'Found {len(deadlines_username)} deadlines for username ArAhis')
    for dl in deadlines_username:
        print(f'  - {dl.title} (Due: {dl.due_date}, People: {dl.user_identifier})')

    print('\nTesting fetch_user_deadlines with no filter:')
    deadlines_all = await fetch_user_deadlines(None)
    print(f'Found {len(deadlines_all)} total deadlines')
    
    print('\nChecking all deadlines that contain ArAhis:')
    for dl in deadlines_all:
        if dl.user_identifier and 'ArAhis' in dl.user_identifier:
            print(f'  - {dl.title} (Due: {dl.due_date}, People: {dl.user_identifier})')

if __name__ == "__main__":
    asyncio.run(test_csv())
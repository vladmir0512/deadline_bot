from datetime import UTC, datetime
from services import get_user_deadlines

# Get the test user ID (VJ_Games has user ID 2 in our database)
user_id = 2

# Test the function with the new include_no_date parameter
deadlines = get_user_deadlines(user_id, status="active", only_future=True, include_no_date=True)
print(f'With include_no_date=True, found {len(deadlines)} deadlines:')
for d in deadlines:
    print(f'  ID: {d.id}, Title: {d.title}, Due: {d.due_date}')

print()

# Test with include_no_date=False to compare
deadlines_false = get_user_deadlines(user_id, status="active", only_future=True, include_no_date=False)
print(f'With include_no_date=False, found {len(deadlines_false)} deadlines:')
for d in deadlines_false:
    print(f'  ID: {d.id}, Title: {d.title}, Due: {d.due_date}')
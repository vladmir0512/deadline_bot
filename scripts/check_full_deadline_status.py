from db import SessionLocal
from models import Deadline
from services import get_user_by_telegram_id
from models import DeadlineStatus

# Check user with telegram_id 929644995 (vj_games)
user = get_user_by_telegram_id(929644995)
print(f'Checking all deadlines for user {user.username} (ID: {user.id}):')

session = SessionLocal()
try:
    # Get ALL deadlines for the user (regardless of status)
    all_user_deadlines = session.query(Deadline).filter_by(user_id=user.id).order_by(Deadline.id).all()
    print(f'Found {len(all_user_deadlines)} total deadlines in database:')
    for i, dl in enumerate(all_user_deadlines):
        print(f'  {i+1}. ID:{dl.id} - {dl.title} (Due: {dl.due_date}, Source: {dl.source}, Status: {dl.status})')
    
    print()
    
    # Check only active deadlines
    active_deadlines = session.query(Deadline).filter_by(user_id=user.id, status=DeadlineStatus.ACTIVE).all()
    print(f'Found {len(active_deadlines)} ACTIVE deadlines in database:')
    for i, dl in enumerate(active_deadlines):
        print(f'  {i+1}. ID:{dl.id} - {dl.title} (Due: {dl.due_date}, Source: {dl.source}, Status: {dl.status})')
    
    print()
    
    # Check non-active deadlines
    inactive_deadlines = session.query(Deadline).filter(
        Deadline.user_id == user.id,
        Deadline.status != DeadlineStatus.ACTIVE
    ).all()
    print(f'Found {len(inactive_deadlines)} INACTIVE deadlines in database:')
    for i, dl in enumerate(inactive_deadlines):
        print(f'  {i+1}. ID:{dl.id} - {dl.title} (Due: {dl.due_date}, Source: {dl.source}, Status: {dl.status})')
        
    print()
    
    # Check Yonote source deadlines specifically
    yonote_deadlines = session.query(Deadline).filter_by(user_id=user.id, source="yonote").all()
    print(f'Found {len(yonote_deadlines)} YONOTE deadlines in database:')
    for i, dl in enumerate(yonote_deadlines):
        print(f'  {i+1}. ID:{dl.id} - {dl.title} (Due: {dl.due_date}, Status: {dl.status})')
        
finally:
    session.close()

print()
print("--- NOW CHECKING WHAT THE MY_DEADLINES COMMAND WOULD SHOW ---")

# Simulate what get_user_deadlines returns (what /mydeadlines uses)
from services import get_user_deadlines

# Get deadlines the same way as the my_deadlines command
user_deadlines = get_user_deadlines(user.id, status="active", only_future=True, include_no_date=True)
print(f'get_user_deadlines returns {len(user_deadlines)} deadlines:')
for i, dl in enumerate(user_deadlines):
    print(f'  {i+1}. {dl.title} (Due: {dl.due_date})')
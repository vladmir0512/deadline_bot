import os
from scripts.yonote_csv_client import YonoteCsvClient
import asyncio

if not os.getenv("YONOTE_API_KEY") or not os.getenv("YONOTE_CALENDAR_ID"):
    print("YONOTE_API_KEY или YONOTE_CALENDAR_ID не заданы, пропускаю тест.")
    exit(0)

# Test the CSV API directly to see what it returns
async def test_csv_data():
    client = YonoteCsvClient()
    csv_content = await client.fetch_deadlines_raw_csv()
    raw_data = client.parse_csv_to_deadlines(csv_content)
    
    # See what deadlines are assigned to our user 'vj_games' 
    user_deadlines = []
    for deadline in raw_data:
        if deadline.user_identifier and 'vj_games' in deadline.user_identifier.lower():
            user_deadlines.append(deadline)
    
    print(f"Found {len(user_deadlines)} deadlines in CSV assigned to 'vj_games':")
    for dl in user_deadlines:
        print(f"  - {dl.title} (Due: {dl.due_date}, People: {dl.user_identifier})")
    
    # Get titles of deadlines for our user
    user_titles = {dl.title for dl in user_deadlines}
    print(f"\nSet of titles from CSV: {user_titles}")
    
    # Compare with what's in the database for user ID 4 (vj_games)
    from db import SessionLocal
    from models import Deadline
    
    session = SessionLocal()
    try:
        db_deadlines = session.query(Deadline).filter_by(user_id=4, source="yonote").all()
        db_titles = {dl.title for dl in db_deadlines}
        print(f"Set of titles in database: {db_titles}")
        
        # Find which titles are in database but not in CSV (these should be deleted)
        to_delete = db_titles - user_titles
        print(f"Titles to delete from database: {to_delete}")
        
        # Find which titles are in CSV but not in database (these should be created)
        to_create = user_titles - db_titles
        print(f"Titles to create in database: {to_create}")
        
    finally:
        session.close()

asyncio.run(test_csv_data())
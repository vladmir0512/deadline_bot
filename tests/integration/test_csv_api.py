#!/usr/bin/env python3
"""
Test CSV export API from Yonote
"""

import os
import sys
import csv
import io
import requests
from dotenv import load_dotenv

# Load environment
load_dotenv()

YONOTE_API_KEY = os.getenv("YONOTE_API_KEY")  
YONOTE_CALENDAR_ID = os.getenv("YONOTE_CALENDAR_ID")  # This should be the database ID

def safe_print(*args, **kwargs):
    """Печать с защитой от UnicodeEncodeError в cp1251-консоли."""
    text = " ".join(str(a) for a in args)
    try:
        print(text, **kwargs)
    except UnicodeEncodeError:
        print(text.encode("cp1251", "replace").decode("cp1251"), **kwargs)

def test_csv_export():
    """Test the CSV export API to see if it provides better data structure"""
    
    if not YONOTE_API_KEY or not YONOTE_CALENDAR_ID:
        safe_print("ERROR: YONOTE_API_KEY or YONOTE_CALENDAR_ID not set in environment")
        return
    
    # Build the CSV export URL
    csv_url = "https://app.yonote.ru/api/database.export_csv"
    
    params = {
        "databaseId": YONOTE_CALENDAR_ID,
        "token": YONOTE_API_KEY
    }
    
    safe_print(f"Requesting CSV export from: {csv_url}")
    safe_print(f"Params: {params}")
    
    try:
        response = requests.get(csv_url, params=params)
        response.raise_for_status()
        
        safe_print(f"Response status: {response.status_code}")
        safe_print(f"Response headers: {dict(response.headers)}")

        # Try to parse the CSV content - handle encoding properly (strip BOM)
        csv_content = response.content.decode('utf-8-sig')
        safe_print(f"\nRaw CSV content preview (first 500 chars):\n{repr(csv_content[:500])}")

        # Parse the CSV
        csv_io = io.StringIO(csv_content)
        reader = csv.DictReader(csv_io, delimiter=";")

        safe_print(f"\nCSV field names: {reader.fieldnames}")

        safe_print(f"\nFirst few rows:")
        for i, row in enumerate(reader):
            if i >= 5:  # Show first 5 rows
                break
            safe_print(f"Row {i+1}: {row}")
        
        # Reset to check for 'people' like fields
        csv_io = io.StringIO(csv_content)
        reader = csv.DictReader(csv_io, delimiter=";")
        
        safe_print(f"\nLooking for people-related fields...")
        people_like_fields = []
        for field in reader.fieldnames:
            field_lower = field.lower()
            if any(keyword in field_lower for keyword in ["люди", "people", "person", "участник", "member", "assign", "назначен", "email", "user", "ник"]):
                people_like_fields.append(field)
        
        if people_like_fields:
            safe_print(f"Found potential people fields: {people_like_fields}")
            
            # Show sample data for these fields
            csv_io = io.StringIO(csv_content)
            reader = csv.DictReader(csv_io, delimiter=";")
            for i, row in enumerate(reader):
                if i >= 5:  # Show first 5 rows
                    break
                safe_print(f"Row {i+1} people data:")
                for field in people_like_fields:
                    if field in row:
                        safe_print(f"  {field}: {row[field]}")
                safe_print()
        else:
            safe_print("No obvious people-related fields found")
            
        # Also look for date-related fields
        csv_io = io.StringIO(csv_content)
        reader = csv.DictReader(csv_io, delimiter=";")
        
        safe_print(f"\nLooking for date-related fields...")
        date_like_fields = []
        for field in reader.fieldnames:
            field_lower = field.lower()
            if any(keyword in field_lower for keyword in ["дата", "date", "due", "deadline", "end", "start", "время"]):
                date_like_fields.append(field)
        
        if date_like_fields:
            safe_print(f"Found potential date fields: {date_like_fields}")
            
            # Show sample data for these fields
            csv_io = io.StringIO(csv_content)
            reader = csv.DictReader(csv_io, delimiter=";")
            for i, row in enumerate(reader):
                if i >= 3:  # Show first 3 rows
                    break
                safe_print(f"Row {i+1} date data:")
                for field in date_like_fields:
                    if field in row:
                        safe_print(f"  {field}: {row[field]}")
                safe_print()
                        
    except requests.exceptions.RequestException as e:
        safe_print(f"Request error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            safe_print(f"Response content: {e.response.text[:500]}...")
    except Exception as e:
        safe_print(f"Error processing CSV: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_csv_export()
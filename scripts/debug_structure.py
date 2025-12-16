#!/usr/bin/env python3
"""
Test script to analyze Yonote structure using existing environment
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add current directory to path to import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from yonote_client import YonoteClient

async def analyze_yonote_structure():
    """Analyze the structure of Yonote API response to better identify people fields"""
    print("=== Analyzing Yonote API response structure ===")
    
    client = YonoteClient()
    
    try:
        print("Fetching raw data from Yonote...")
        raw_data = await client.fetch_deadlines_raw()
        
        print(f"Type of raw_data: {type(raw_data)}")
        
        if isinstance(raw_data, dict):
            print(f"Raw data keys: {raw_data.keys() if raw_data.keys() else 'No keys'}")
            
            if "data" in raw_data:
                items = raw_data["data"]
                print(f"Found {len(items) if isinstance(items, list) else 'not a list'} items in 'data' field")
            elif isinstance(raw_data, list):
                items = raw_data
                print(f"Raw data is a list with {len(items)} items")
            else:
                print("Unexpected data structure")
                return
        
            if items and isinstance(items, list) and len(items) > 0:
                print(f"\nAnalyzing first item structure...")
                first_item = items[0]
                print(f"First item type: {type(first_item)}")
                
                if isinstance(first_item, dict):
                    print(f"First item keys: {list(first_item.keys())}")
                    
                    # Look at properties
                    properties = first_item.get("properties", {})
                    print(f"\nProperties: {properties}")
                    
                    # Look at values
                    values = first_item.get("values", {})
                    print(f"\nValues structure:")
                    for key, value in values.items():
                        print(f"  {key}: {type(value)} = {value}")
                        
                    # Look for potential people fields
                    print(f"\nSearching for people fields...")
                    for prop_id, prop_data in properties.items():
                        if isinstance(prop_data, dict):
                            prop_name = prop_data.get("name", "").lower()
                            prop_type = prop_data.get("type", prop_data.get("property_type", "")).lower()
                            
                            print(f"  Property {prop_id}: name='{prop_name}', type='{prop_type}'")
                            
                            if any(keyword in prop_name for keyword in ["люди", "people", "person", "member", "assign", "назначен"]):
                                print(f"    -> POTENTIAL PEOPLE FIELD: {prop_id}")
                    
                    # Check values for people
                    for val_id, val_data in values.items():
                        if isinstance(val_data, list):
                            # Check if this could be a people list
                            if val_data and isinstance(val_data[0], dict):
                                first_elem = val_data[0]
                                if any(key in first_elem for key in ["name", "id", "email", "label"]):
                                    print(f"  -> POTENTIAL PEOPLE LIST in values[{val_id}]: {val_data}")
                        elif isinstance(val_data, str) and ("," in val_data or "@" in val_data):
                            print(f"  -> POTENTIAL PEOPLE STRING in values[{val_id}]: {val_data}")
        
        print(f"\nNow let's see what the current parser finds...")
        parsed = client.parse_deadlines(raw_data)
        print(f"Parsed {len(parsed)} deadlines")
        
        for i, deadline in enumerate(parsed[:3]):  # First 3
            print(f"  {i+1}. Title: {deadline.title}")
            print(f"     User Identifier: {deadline.user_identifier}")
            print(f"     Due Date: {deadline.due_date}")
            print()
        
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(analyze_yonote_structure())
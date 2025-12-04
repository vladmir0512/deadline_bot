"""
Enhanced debug script to understand Yonote calendar structure and specifically identify the 'люди' field.
"""

import asyncio
import json
from yonote_client import YonoteClient


async def debug_yonote_structure():
    """Debug function to print detailed structure of Yonote data."""
    client = YonoteClient()
    
    print("Fetching raw data from Yonote...")
    try:
        raw_data = await client.fetch_deadlines_raw()
        print("Successfully fetched raw data")
        
        # Print the overall structure
        print("\nRaw data structure:")
        if isinstance(raw_data, dict):
            print(f"  Keys in root: {list(raw_data.keys())}")
            if "data" in raw_data:
                print(f"  Length of 'data' array: {len(raw_data['data'])}")
                
                # Print all items to inspect the 'люди' field
                for i, item in enumerate(raw_data['data']):
                    print(f"\n  --- Item {i+1} ---")
                    if isinstance(item, dict):
                        title = item.get("title", "N/A")
                        print(f"  Title: {title}")
                        
                        # Print all values to identify the 'люди' field
                        values = item.get("values") or {}
                        print(f"  Values keys: {list(values.keys())}")
                        
                        for key, val in values.items():
                            print(f"    '{key}': {type(val).__name__} = {repr(val)}")
        
        print("\n" + "="*50)
        print("SUMMARY OF ALL FIELD KEYS ACROSS ITEMS:")
        
        # Collect all unique field keys
        all_field_keys = set()
        for item in raw_data.get('data', []):
            if isinstance(item, dict):
                values = item.get('values', {})
                all_field_keys.update(values.keys())
        
        print(f"All unique field keys found: {list(all_field_keys)}")
        
        # Check for likely 'люди' fields (look for fields that might contain names/emails)
        print("\nAnalyzing potential 'люди' (People) fields:")
        for key in all_field_keys:
            print(f"\nField '{key}':")
            for i, item in enumerate(raw_data.get('data', [])):
                values = item.get('values', {})
                field_value = values.get(key)
                title = item.get('title', 'N/A')
                print(f"  Item '{title}': {repr(field_value)}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_yonote_structure())
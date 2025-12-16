"""
Debug script to understand Yonote calendar structure and identify the 'люди' field.
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

                # Print first few items for inspection
                for i, item in enumerate(raw_data['data'][:3]):  # First 3 items only
                    print(f"\n  --- Item {i+1} ---")
                    if isinstance(item, dict):
                        print(f"  Item keys: {list(item.keys())}")

                        # Print properties if available
                        if "properties" in item:
                            print(f"  Properties: {json.dumps(item['properties'], indent=2, ensure_ascii=False)[:500]}...")

                        # Print values if available
                        if "values" in item:
                            print(f"  Values keys: {list(item['values'].keys())}")
                            values = item['values']
                            for key, val in list(values.items())[:5]:  # First 5 values only
                                print(f"    '{key}': {type(val).__name__} = {str(val)[:200]}")

                        # Print title for reference
                        title = item.get("title", "N/A")
                        print(f"  Title: {title}")

        # Parse deadlines to see what gets extracted
        print("\nParsing deadlines...")
        parsed_deadlines = client.parse_deadlines(raw_data)
        print(f"Successfully parsed {len(parsed_deadlines)} deadlines")

        for i, deadline in enumerate(parsed_deadlines[:5]):  # First 5 deadlines only
            print(f"\n  Deadline {i+1}:")
            print(f"    Title: {deadline.title}")
            print(f"    User identifier: {deadline.user_identifier}")
            print(f"    Due date: {deadline.due_date}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_yonote_structure())
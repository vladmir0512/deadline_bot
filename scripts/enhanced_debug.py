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

        # raw_data сейчас list (CSV-парсер), обработаем универсально
        print("\nRaw data structure:")
        if isinstance(raw_data, dict):
            print(f"  Keys in root: {list(raw_data.keys())}")
            data_items = raw_data.get("data", [])
        elif isinstance(raw_data, list):
            data_items = raw_data
            print(f"  Received list with {len(data_items)} items")
        else:
            data_items = []
            print(f"  Unexpected type: {type(raw_data)}")

        # Печать первых элементов/ключей
        if data_items:
            first = data_items[0]
            if isinstance(first, dict):
                print(f"First item keys: {list(first.keys())}")
            else:
                print(f"First item is not dict: {type(first)}")
        else:
            print("No data returned.")

        # Сбор всех ключей values
        all_field_keys = set()
        for item in data_items:
            if isinstance(item, dict):
                values = item.get("values") or {}
                all_field_keys.update(values.keys())

        print("\n" + "=" * 50)
        print("SUMMARY OF ALL FIELD KEYS ACROSS ITEMS:")
        print(f"All unique field keys found: {list(all_field_keys)}")

        # Проверка возможных 'люди' полей
        print("\nAnalyzing potential 'люди' (People) fields:")
        for key in all_field_keys:
            print(f"\nField '{key}':")
            for i, item in enumerate(data_items[:5]):  # ограничимся первыми 5 для компактности
                if not isinstance(item, dict):
                    continue
                values = item.get("values", {})
                field_value = values.get(key)
                title = item.get("title", "N/A")
                print(f"  Item '{title}': {repr(field_value)}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_yonote_structure())
import aiohttp
import json
from dotenv import load_dotenv
load_dotenv()
import os

YONOTE_BASE_URL = 'https://unikeygroup.yonote.ru/api/v2'
YONOTE_API_KEY = os.getenv('YONOTE_API_KEY')
YONOTE_CALENDAR_ID = os.getenv('YONOTE_CALENDAR_ID')

async def test_v2_api():
    filter_obj = {"parentDocumentId": YONOTE_CALENDAR_ID}

    params = {
        "filter": json.dumps(filter_obj, ensure_ascii=False),
        "limit": "100",
        "offset": "0",
        "sort": '[["tableOrder","ASC"]]',
        "userTimeZone": "Europe/Moscow",
    }

    url = YONOTE_BASE_URL.rstrip("/") + "/database/rows"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {YONOTE_API_KEY}",
    }

    print(f"Requesting v2 API: {url}")
    print(f"Params: {params}")

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            print(f"Status: {resp.status}")
            if resp.status == 200:
                data = await resp.json()
                rows = data.get("data", [])
                print(f"Got {len(rows)} rows")
                if rows:
                    print("First row keys:", list(rows[0].keys()))
                    print("First row sample:", str(rows[0])[:300])
            else:
                text = await resp.text()
                print(f"Error: {text}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_v2_api())

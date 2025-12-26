"""
Простая версия клиента Yonote для тестирования.
"""

import asyncio
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

YONOTE_API_KEY = os.getenv('YONOTE_API_KEY')
YONOTE_CALENDAR_ID = os.getenv('YONOTE_CALENDAR_ID')

async def test_simple():
    """Простой тест - делаем запрос и ждем немного."""
    csv_url = "https://app.yonote.ru/api/database.export_csv"

    params = {
        "id": YONOTE_CALENDAR_ID,
        "token": YONOTE_API_KEY
    }

    print(f"Requesting: {csv_url}")
    print(f"Params: {params}")

    async with aiohttp.ClientSession() as session:
        # Первый запрос
        async with session.get(csv_url, params=params) as resp:
            print(f"First request status: {resp.status}")
            if resp.status == 200:
                try:
                    data = await resp.json()
                    print("Got JSON response")
                    operation_id = data.get('data', {}).get('fileOperation', {}).get('id')
                    print(f"Operation ID: {operation_id}")
                except:
                    text = await resp.text()
                    print("Got text response:")
                    print(text[:500])
                    return

        # Ждем 2 секунды
        await asyncio.sleep(2)

        # Второй запрос
        async with session.get(csv_url, params=params) as resp:
            print(f"Second request status: {resp.status}")
            if resp.status == 200:
                try:
                    data = await resp.json()
                    print("Got JSON response again")
                except:
                    text = await resp.text()
                    print("Got CSV response!")
                    print(f"Length: {len(text)}")
                    print("First 200 chars:")
                    print(repr(text[:200]))
                    return

        # Проверяем статус операции
        if operation_id:
            status_url = f"https://unikeygroup.yonote.ru/api/fileOperations/{operation_id}"
            print(f"Checking status: {status_url}")
            async with session.get(status_url, params={"token": YONOTE_API_KEY}) as status_resp:
                print(f"Status check response: {status_resp.status}")
                if status_resp.status == 200:
                    status_data = await status_resp.json()
                    print("Status data:", status_data)
                else:
                    text = await status_resp.text()
                    print("Status error:", text)

if __name__ == "__main__":
    asyncio.run(test_simple())

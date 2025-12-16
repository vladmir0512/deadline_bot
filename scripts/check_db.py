#!/usr/bin/env python3
"""
Скрипт для проверки содержимого базы данных.
"""

import os
import sqlite3
from pathlib import Path

def check_database():
    # Получаем путь к БД
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        db_path = Path(__file__).parent / 'data' / 'моя_база.db'
    else:
        db_path = db_url.replace('sqlite:///', '') if db_url.startswith('sqlite:///') else db_url

    print(f'Путь к БД: {db_path}')

    if not Path(db_path).exists():
        print('База данных не найдена')
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Проверим структуру таблицы deadlines
    cursor.execute('PRAGMA table_info(deadlines)')
    columns = cursor.fetchall()
    print('Колонки таблицы deadlines:')
    for col in columns:
        print(f'  {col[1]}: {col[2]}')

    # Проверим данные
    cursor.execute('SELECT id, title, due_date, source, source_id FROM deadlines WHERE source="yonote" LIMIT 5')
    rows = cursor.fetchall()
    print(f'\nДедлайны из Yonote ({len(rows)} записей):')
    for row in rows:
        print(f'  ID: {row[0]}, Title: {row[1]}, Due: {row[2]}, Source: {row[3]}, Source_ID: {row[4]}')

    conn.close()

if __name__ == "__main__":
    check_database()

import sqlite3
import os

# Открываем базу данных напрямую
db_path = 'data/deadlines.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Получаем данные из таблицы deadlines
cursor.execute('SELECT id, title FROM deadlines WHERE source = "yonote" LIMIT 5')
rows = cursor.fetchall()

print('Данные из базы данных:')
for row in rows:
    print(f'ID: {row[0]}, Title: {repr(row[1])}')
    if row[1]:
        print(f'  Title bytes: {row[1].encode("utf-8")}')
        print(f'  Title length: {len(row[1])}')

conn.close()

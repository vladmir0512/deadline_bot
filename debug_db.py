#!/usr/bin/env python3
"""
Debug script to check database contents and user deadlines
"""
import os
import sqlite3
from datetime import datetime
from pathlib import Path

def debug_database():
    # Получаем путь к БД из переменной окружения или используем значение по умолчанию
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        # По умолчанию используем ../data/моя_база.db
        default_db_path = Path(__file__).parent.parent / "data" / "моя_база.db"
        db_path = str(default_db_path.resolve())
    elif db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        # Если это относительный путь, преобразуем в абсолютный
        if not os.path.isabs(db_path):
            db_path = str(Path(db_path).resolve())
        # В Windows пути могут содержать обратные слеши, оставляем как есть для sqlite3.connect
    else:
        print(f"[ERROR] Неподдерживаемый формат БД: {db_url}")
        return
    
    print(f"[INFO] Подключение к БД: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=== USERS ===")
    cursor.execute("SELECT id, telegram_id, username, email, created_at FROM users")
    users = cursor.fetchall()
    if users:
        print("ID | Telegram ID | Username | Email | Created At")
        print("-" * 60)
        for user in users:
            print(f"{user[0]} | {user[1]} | {user[2]} | {user[3]} | {user[4]}")
    else:
        print("No users found")
    
    print("\n=== DEADLINES ===")
    # Get all deadlines
    cursor.execute("""
        SELECT d.id, d.user_id, d.title, d.due_date, d.status, d.source, d.created_at, u.username, u.email
        FROM deadlines d
        LEFT JOIN users u ON d.user_id = u.id
        ORDER BY d.due_date
    """)
    deadlines = cursor.fetchall()
    if deadlines:
        print("ID | User ID | Title | Due Date | Status | Source | Created At | Username | Email")
        print("-" * 100)
        for deadline in deadlines:
            print(f"{deadline[0]} | {deadline[1]} | {deadline[2]} | {deadline[3]} | {deadline[4]} | {deadline[5]} | {deadline[6]} | {deadline[7]} | {deadline[8]}")
    else:
        print("No deadlines found")
    
    print("\n=== DEADLINES BY USER ===")
    for user in users:
        user_id, telegram_id, username, email, created_at = user
        print(f"\nUser: {username or email or telegram_id} (DB ID: {user_id})")
        
        cursor.execute("""
            SELECT id, title, due_date, status, source, created_at
            FROM deadlines
            WHERE user_id = ?
            ORDER BY due_date
        """, (user_id,))
        user_deadlines = cursor.fetchall()
        
        if user_deadlines:
            for dl in user_deadlines:
                print(f"  ID: {dl[0]}, Title: {dl[1]}, Due: {dl[2]}, Status: {dl[3]}, Source: {dl[4]}, Created: {dl[5]}")
        else:
            print("  No deadlines for this user")
    
    conn.close()

if __name__ == "__main__":
    debug_database()
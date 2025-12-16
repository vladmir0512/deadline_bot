import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import get_user_by_telegram_id
from scripts.sync_deadlines import sync_user_deadlines
import asyncio

# Получаем пользователя
user = get_user_by_telegram_id(929644995)  # ваш telegram ID
print(f'Синхронизируем для пользователя: ID={user.id}, username={user.username}, email={user.email}')

if user:
    created, updated = asyncio.run(sync_user_deadlines(user))
    print(f'Синхронизация завершена: создано {created}, обновлено {updated}')
    
    # Проверим дедлайны после синхронизации
    from services import get_user_deadlines
    from models import DeadlineStatus
    deadlines = get_user_deadlines(user.id, status=DeadlineStatus.ACTIVE)
    print(f'После синхронизации пользователь {user.username} (ID {user.id}) имеет {len(deadlines)} активных дедлайнов:')
    for dl in deadlines:
        print(f'  - {dl.title} (Due: {dl.due_date})')
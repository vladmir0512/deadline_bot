from services import get_user_deadlines, get_user_by_telegram_id
from models import DeadlineStatus

user = get_user_by_telegram_id(929644995)  # ваш telegram ID
print(f'Проверяем пользователя: ID={user.id}, username={user.username}, email={user.email}')

user_deadlines = get_user_deadlines(user.id, status=DeadlineStatus.ACTIVE)
print(f'Пользователь {user.username} (ID {user.id}) теперь имеет {len(user_deadlines)} активных дедлайнов:')
for dl in user_deadlines:
    print(f'  - {dl.title} (Due: {dl.due_date})')
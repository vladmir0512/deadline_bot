from services import get_user_by_telegram_id
from db import SessionLocal

# Обновим пользователя с telegram_id 929644995, чтобы он снова стал ArAhis
user = get_user_by_telegram_id(929644995)

if user:
    print(f'Текущий ник: {user.username}')
    user.username = 'ArAhis'
    
    session = SessionLocal()
    try:
        session.add(user)
        session.commit()
        print(f'Ник успешно изменен на ArAhis')
    finally:
        session.close()
        
    print(f'Теперь пользователь: ID={user.id}, username={user.username}, email={user.email}')
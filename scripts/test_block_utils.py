#!/usr/bin/env python3
"""
Тест функций блокировки пользователей.
"""

import sys
from pathlib import Path

# Добавляем корневую директорию в путь для импортов
sys.path.insert(0, str(Path(__file__).parent.parent))

from block_utils import get_blocked_users, is_user_blocked, block_user, unblock_user


def test_block_utils():
    """Тест функций блокировки."""
    print("TEST: Тестирование функций блокировки пользователей")
    print("=" * 50)

    # Тест 1: Получение пустого списка
    print("1. Тест получения пустого списка заблокированных...")
    blocked = get_blocked_users()
    print(f"   Заблокированные пользователи: {blocked}")
    assert len(blocked) == 0, "Список должен быть пустым"
    print("   [OK]")

    # Тест 2: Проверка блокировки несуществующего пользователя
    print("2. Тест проверки блокировки несуществующего пользователя...")
    assert not is_user_blocked(123456789), "Пользователь не должен быть заблокирован"
    print("   [OK]")

    # Тест 3: Блокировка пользователя
    print("3. Тест блокировки пользователя...")
    success = block_user(123456789)
    assert success, "Блокировка должна быть успешной"
    assert is_user_blocked(123456789), "Пользователь должен быть заблокирован"
    print("   [OK]")

    # Тест 4: Получение списка с одним пользователем
    print("4. Тест получения списка с одним заблокированным...")
    blocked = get_blocked_users()
    assert 123456789 in blocked, "Пользователь должен быть в списке"
    assert len(blocked) == 1, "Должен быть один заблокированный пользователь"
    print(f"   Заблокированные пользователи: {blocked}")
    print("   [OK]")

    # Тест 5: Повторная блокировка того же пользователя
    print("5. Тест повторной блокировки...")
    success = block_user(123456789)
    assert success, "Повторная блокировка должна быть успешной"
    blocked = get_blocked_users()
    assert len(blocked) == 1, "Должен остаться один пользователь"
    print("   [OK]")

    # Тест 6: Блокировка второго пользователя
    print("6. Тест блокировки второго пользователя...")
    success = block_user(987654321)
    assert success, "Блокировка должна быть успешной"
    blocked = get_blocked_users()
    assert len(blocked) == 2, "Должно быть два пользователя"
    assert 123456789 in blocked and 987654321 in blocked, "Оба пользователя должны быть в списке"
    print(f"   Заблокированные пользователи: {blocked}")
    print("   [OK]")

    # Тест 7: Разблокировка пользователя
    print("7. Тест разблокировки пользователя...")
    success = unblock_user(123456789)
    assert success, "Разблокировка должна быть успешной"
    assert not is_user_blocked(123456789), "Пользователь не должен быть заблокирован"
    blocked = get_blocked_users()
    assert len(blocked) == 1, "Должен остаться один пользователь"
    assert 987654321 in blocked, "Второй пользователь должен остаться"
    print(f"   Заблокированные пользователи: {blocked}")
    print("   [OK]")

    # Тест 8: Разблокировка несуществующего пользователя
    print("8. Тест разблокировки несуществующего пользователя...")
    success = unblock_user(999999999)
    assert success, "Разблокировка несуществующего пользователя должна быть успешной"
    blocked = get_blocked_users()
    assert len(blocked) == 1, "Количество не должно измениться"
    print("   [OK]")

    # Тест 9: Очистка всех блокировок
    print("9. Тест очистки всех блокировок...")
    success = unblock_user(987654321)
    assert success, "Разблокировка должна быть успешной"
    blocked = get_blocked_users()
    assert len(blocked) == 0, "Список должен быть пустым"
    print(f"   Заблокированные пользователи: {blocked}")
    print("   [OK]")

    print("\nSUCCESS: Все тесты пройдены успешно!")
    return True


if __name__ == "__main__":
    try:
        test_block_utils()
        print("\n[OK] Функции блокировки работают корректно!")
    except Exception as e:
        print(f"\n[ERROR] Ошибка в тестах: {e}")
        sys.exit(1)

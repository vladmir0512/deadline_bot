#!/usr/bin/env python3
"""
Скрипт для проверки состояния развертывания deadline_bot.
"""

import os
import sys
import json
import subprocess
from datetime import datetime

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_command(cmd, capture_output=True):
    """Выполняет команду и возвращает результат."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=capture_output, text=True)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def check_docker_containers():
    """Проверяет статус Docker контейнеров."""
    print("[INFO] Проверка Docker контейнеров...")

    success, stdout, stderr = run_command("docker ps --filter name=deadline --format json")
    if not success:
        return False, "Не удалось получить статус контейнеров"

    containers = [json.loads(line) for line in stdout.split('\n') if line.strip()]
    if not containers:
        return False, "Контейнеры не найдены"

    results = []
    for container in containers:
        name = container.get('Names', 'Unknown')
        status = container.get('Status', 'Unknown')
        state = container.get('State', 'Unknown')

        results.append(f"{name}: {status} ({state})")

        if state != 'running':
            return False, f"Контейнер {name} не запущен"

    return True, "\n".join(results)

def check_health_endpoints():
    """Проверяет health check эндпоинты."""
    print("[INFO] Проверка health check эндпоинтов...")

    endpoints = [
        ("http://localhost:8080/health", "Основной health check"),
        ("http://localhost:8081/health", "Health check сервер")
    ]

    results = []
    all_healthy = True

    for url, description in endpoints:
        success, stdout, stderr = run_command(f"curl -s -f {url}")
        if success:
            try:
                data = json.loads(stdout)
                status = data.get('status', 'unknown')
                if status == 'healthy':
                    results.append(f"[OK] {description}: {status}")
                else:
                    results.append(f"[WARN] {description}: {status}")
                    all_healthy = False
            except:
                results.append(f"[WARN] {description}: невалидный JSON")
                all_healthy = False
        else:
            results.append(f"[ERROR] {description}: недоступен")
            all_healthy = False

    return all_healthy, "\n".join(results)

def check_database():
    """Проверяет подключение к базе данных."""
    print("[INFO] Проверка базы данных...")

    try:
        from sqlalchemy import text
        from db import SessionLocal
        session = SessionLocal()
        session.execute(text("SELECT COUNT(*) FROM users"))
        session.close()
        return True, "База данных доступна"
    except Exception as e:
        return False, f"Ошибка подключения к БД: {e}"

def check_logs():
    """Проверяет наличие и размер лог файлов."""
    print("[INFO] Проверка лог файлов...")

    log_files = [
        "logs/bot.log",
        "logs/error.log"
    ]

    results = []
    for log_file in log_files:
        if os.path.exists(log_file):
            size = os.path.getsize(log_file)
            size_mb = size / (1024 * 1024)
            results.append(f"[OK] {log_file}: {size_mb:.2f} MB")
        else:
            results.append(f"[WARN] {log_file}: файл не найден")

    return True, "\n".join(results)

def check_configuration():
    """Проверяет конфигурацию приложения."""
    print("[INFO] Проверка конфигурации...")

    required_env_vars = [
        'TELEGRAM_BOT_TOKEN',
        'YONOTE_API_KEY',
        'DATABASE_URL'
    ]

    results = []
    all_configured = True

    for var in required_env_vars:
        if os.getenv(var):
            results.append(f"[OK] {var}: настроен")
        else:
            results.append(f"[ERROR] {var}: не настроен")
            all_configured = False

    return all_configured, "\n".join(results)

def main():
    """Главная функция проверки."""
    print("=" * 60)
    print("ПРОВЕРКА СОСТОЯНИЯ РАЗВЕРТЫВАНИЯ DEADLINE BOT")
    print("=" * 60)
    print(f"Время проверки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    checks = [
        ("Конфигурация", check_configuration),
        ("База данных", check_database),
        ("Docker контейнеры", check_docker_containers),
        ("Health эндпоинты", check_health_endpoints),
        ("Лог файлы", check_logs),
    ]

    results = []
    overall_success = True

    for check_name, check_func in checks:
        try:
            success, details = check_func()
            results.append((check_name, success, details))
            if not success:
                overall_success = False
        except Exception as e:
            results.append((check_name, False, f"Ошибка выполнения проверки: {e}"))
            overall_success = False
        print()

    # Итоговый отчет
    print("=" * 60)
    print("ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 60)

    for check_name, success, details in results:
        status = "[OK] ПРОЙДЕНО" if success else "[ERROR] ОШИБКА"
        print(f"{status}: {check_name}")
        if details:
            for line in details.split('\n'):
                print(f"  {line}")
        print()

    print("=" * 60)
    if overall_success:
        print("[SUCCESS] Все проверки пройдены! Система работает корректно.")
        sys.exit(0)
    else:
        print("[WARN] Обнаружены проблемы. Проверьте детали выше.")
        sys.exit(1)

if __name__ == "__main__":
    main()

"""
Простой health check сервер для deadline_bot.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

from aiohttp import web
from dotenv import load_dotenv

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import SessionLocal
from logging_config import setup_logging
from version import get_version

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logger = setup_logging(os.getenv("LOG_LEVEL", "INFO"))

class HealthChecker:
    """Класс для проверки здоровья приложения."""

    def __init__(self):
        self.start_time = datetime.now(timezone.utc)
        self.last_sync_check = None
        self.last_notification_check = None

    def update_sync_status(self):
        """Обновляет время последней успешной синхронизации."""
        self.last_sync_check = datetime.now(timezone.utc)

    def update_notification_status(self):
        """Обновляет время последней успешной проверки уведомлений."""
        self.last_notification_check = datetime.now(timezone.utc)

    def get_health_status(self) -> dict:
        """Возвращает статус здоровья приложения."""
        now = datetime.now(timezone.utc)

        # Проверяем подключение к БД
        db_healthy = self._check_database()

        # Проверяем основные компоненты
        components = {
            "database": {
                "status": "healthy" if db_healthy else "unhealthy",
                "details": "Database connection OK" if db_healthy else "Database connection failed"
            },
            "bot": {
                "status": "healthy",
                "details": "Bot is running"
            }
        }

        # Определяем общий статус
        overall_status = "healthy"
        for component in components.values():
            if component["status"] != "healthy":
                overall_status = "unhealthy"
                break

        return {
            "status": overall_status,
            "timestamp": now.isoformat(),
            "uptime_seconds": (now - self.start_time).total_seconds(),
            "version": get_version(),
            "components": components,
            "last_sync": self.last_sync_check.isoformat() if self.last_sync_check else None,
            "last_notification_check": self.last_notification_check.isoformat() if self.last_notification_check else None
        }

    def _check_database(self) -> bool:
        """Проверяет подключение к базе данных."""
        try:
            from sqlalchemy import text
            session = SessionLocal()
            session.execute(text("SELECT 1"))
            session.close()
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

# Глобальный экземпляр health checker
health_checker = HealthChecker()

async def health_handler(request):
    """Обработчик health check запроса."""
    status = health_checker.get_health_status()

    # Возвращаем соответствующий HTTP статус
    http_status = 200 if status["status"] == "healthy" else 503

    return web.json_response(status, status=http_status)

async def readiness_handler(request):
    """Обработчик readiness запроса."""
    # Readiness проверяет, готов ли сервис принимать трафик
    db_healthy = health_checker._check_database()

    if db_healthy:
        return web.json_response({"status": "ready"})
    else:
        return web.json_response({"status": "not ready"}, status=503)

async def create_app():
    """Создает aiohttp приложение."""
    app = web.Application()

    app.router.add_get("/health", health_handler)
    app.router.add_get("/ready", readiness_handler)

    logger.info("Health check server created")
    return app

async def run_health_server():
    """Запускает health check сервер."""
    app = await create_app()

    # Получаем порт из переменных окружения или используем 8080 по умолчанию
    port = int(os.getenv("HEALTH_CHECK_PORT", "8080"))
    host = os.getenv("HEALTH_CHECK_HOST", "0.0.0.0")

    logger.info(f"Starting health check server on {host}:{port}")

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, host, port)
    await site.start()

    logger.info(f"Health check server started on http://{host}:{port}")

    # Держим сервер запущенным
    try:
        while True:
            await asyncio.sleep(3600)  # Проверяем каждый час
    except KeyboardInterrupt:
        logger.info("Stopping health check server...")
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(run_health_server())


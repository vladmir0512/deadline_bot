"""
Конфигурация логирования для deadline_bot.
"""

import logging
import logging.handlers
import os
from pathlib import Path

# Создаем директорию для логов
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Настройка форматтеров
detailed_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
)

simple_formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s"
)

# Консольный handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(simple_formatter)

# Определяем имя файла логов на основе скрипта или переменной окружения
import sys
script_name = sys.argv[0].split('/')[-1].replace('.py', '') if len(sys.argv) > 0 else 'unknown'
service_name = os.getenv('SERVICE_NAME', script_name)

# Файловый handler с ротацией (с обработкой ошибок доступа)
try:
    logs_dir.mkdir(exist_ok=True)

    # Используем разные файлы для разных сервисов
    log_filename = f"{service_name}.log"

    file_handler = logging.handlers.RotatingFileHandler(
        logs_dir / log_filename,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    file_handler_available = True
except (PermissionError, OSError) as e:
    print(f"Warning: Cannot create log file handler for {service_name}: {e}")
    file_handler = None
    file_handler_available = False

# Handler для ошибок (с обработкой ошибок доступа)
try:
    if not file_handler_available:
        logs_dir.mkdir(exist_ok=True)

    error_filename = f"{service_name}_error.log"

    error_handler = logging.handlers.RotatingFileHandler(
        logs_dir / error_filename,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    error_handler_available = True
except (PermissionError, OSError) as e:
    print(f"Warning: Cannot create error log file handler for {service_name}: {e}")
    error_handler = None
    error_handler_available = False

def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Настройка логирования для приложения.

    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Logger instance
    """
    # Получаем числовое значение уровня логирования
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Настраиваем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Очищаем существующие handlers
    root_logger.handlers.clear()

    # Добавляем handlers
    root_logger.addHandler(console_handler)
    if file_handler_available and file_handler:
        root_logger.addHandler(file_handler)
    if error_handler_available and error_handler:
        root_logger.addHandler(error_handler)

    # Создаем логгер для приложения
    logger = logging.getLogger("deadline_bot")
    logger.setLevel(numeric_level)

    return logger

def log_startup_info(logger: logging.Logger, config: dict) -> None:
    """Логирует информацию о запуске приложения."""
    logger.info("=" * 50)
    logger.info("DEADLINE BOT STARTING UP")
    logger.info("=" * 50)
    logger.info(f"Database URL: {config.get('database_url', 'Not configured')}")
    logger.info(f"Telegram Bot Token: {'Configured' if config.get('bot_token') else 'Not configured'}")
    logger.info(f"Yonote API Key: {'Configured' if config.get('yonote_api_key') else 'Not configured'}")
    logger.info(f"Update Interval: {config.get('update_interval', 'Not configured')} minutes")
    logger.info(f"Log Level: {config.get('log_level', 'INFO')}")
    logger.info("=" * 50)

def log_error_with_context(logger: logging.Logger, error: Exception, context: str = "") -> None:
    """Логирует ошибку с дополнительным контекстом."""
    logger.error(f"{context}: {error}")
    logger.error(f"Error type: {type(error).__name__}")
    if hasattr(error, '__traceback__'):
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

class HealthCheckFilter(logging.Filter):
    """Фильтр для исключения health check запросов из логов."""

    def filter(self, record):
        # Исключаем логи health check
        if hasattr(record, 'getMessage'):
            message = record.getMessage()
            if "health check" in message.lower() or "healthcheck" in message.lower():
                return False
        return True


# Используем официальный Python образ как базовый
FROM python:3.11-slim

# Устанавливаем системные зависимости
RUN apt-get update --fix-missing && apt-get install -y \
    gcc \
    curl \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем requirements.txt и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код приложения
COPY . .

# Создаем директории для данных и логов
RUN mkdir -p data logs

# Устанавливаем переменные окружения по умолчанию
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:///data/deadlines.db

# Создаем пользователя для запуска приложения (без root прав)
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Проверяем здоровье приложения
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.path.insert(0, '.'); from db import SessionLocal; SessionLocal().close(); print('OK')" || exit 1

# Запускаем бота
CMD ["python", "bot.py"]

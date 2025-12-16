# Руководство по развертыванию Deadline Bot

## Обзор

Deadline Bot может быть развернут различными способами: от локального запуска до production deployment на облачных платформах.

## Быстрый старт с Docker

### Предварительные требования

- Docker и Docker Compose
- Токен Telegram бота
- Ключ API Yonote
- ID календаря Yonote

### Шаг 1: Клонирование репозитория

```bash
git clone <repository-url>
cd deadline_bot
```

### Шаг 2: Настройка переменных окружения

Создайте файл `.env`:

```env
# Telegram Bot
TELEGRAM_BOT_TOKEN=ваш_токен_бота

# Yonote API
YONOTE_API_KEY=ваш_ключ_api
YONOTE_CALENDAR_ID=id_календаря
YONOTE_TIMEZONE=Europe/Moscow

# База данных
DATABASE_URL=sqlite:///../data/deadlines.db

# Настройки бота
UPDATE_INTERVAL_MINUTES=30
TELEGRAM_ADMIN_IDS=123456789,987654321

# Логирование
LOG_LEVEL=INFO

# Health check
HEALTH_CHECK_PORT=8080
HEALTH_CHECK_HOST=0.0.0.0
```

### Шаг 3: Запуск

```bash
# Сборка и запуск
docker-compose up -d

# Проверка логов
docker-compose logs -f deadline-bot

# Проверка здоровья
curl http://localhost:8080/health
```

## Production Deployment

### Переход с systemd

Если вы раньше использовали systemd, вот как это соответствует Docker:

**systemd → Docker аналогии:**
```
[Service]
User=root              → USER app (в Dockerfile - безопасный пользователь)
WorkingDirectory=/var/www/ → WORKDIR /app (в Dockerfile)
Environment=...        → environment: секция в docker-compose.yml
ExecStart=/path/to/bot → command: ["python", "bot.py"]
Restart=always         → restart: unless-stopped
```

**systemd с Docker:**
```bash
# Создайте /etc/systemd/system/deadline-bot.service
sudo cp systemd-example.service /etc/systemd/system/deadline-bot.service
sudo systemctl enable deadline-bot
sudo systemctl start deadline-bot
```

### Вариант 1: Railway

1. Подключите GitHub репозиторий к Railway
2. Добавьте переменные окружения в Railway dashboard
3. Railway автоматически соберет и запустит приложение

### Вариант 2: VPS с Docker

```bash
# На сервере
git clone <repository-url>
cd deadline_bot

# Создайте .env файл
nano .env

# Запуск
docker-compose up -d

# Настройка nginx (опционально)
sudo apt install nginx
sudo nano /etc/nginx/sites-available/deadline-bot

# Конфигурация nginx для health check
server {
    listen 80;
    server_name your-domain.com;

    location /health {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Вариант 3: Самостоятельный хостинг

```bash
# Установка зависимостей
sudo apt update
sudo apt install python3 python3-pip sqlite3

# Настройка виртуального окружения
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Создание systemd service
sudo nano /etc/systemd/system/deadline-bot.service

[Unit]
Description=Deadline Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/path/to/deadline_bot
Environment=PATH=/path/to/deadline_bot/venv/bin
ExecStart=/path/to/deadline_bot/venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target

# Запуск сервиса
sudo systemctl enable deadline-bot
sudo systemctl start deadline-bot
sudo systemctl status deadline-bot
```

## Мониторинг и обслуживание

### Health Check эндпоинты

- `GET /health` - Полная проверка здоровья
- `GET /ready` - Проверка готовности к работе

Пример ответа:

```json
{
  "status": "healthy",
  "timestamp": "2025-12-16T15:30:00Z",
  "uptime_seconds": 3600,
  "version": "1.0.0",
  "components": {
    "database": {
      "status": "healthy",
      "details": "Database connection OK"
    },
    "bot": {
      "status": "healthy",
      "details": "Bot is running"
    }
  }
}
```

### Логи

Логи сохраняются в директории `logs/`:
- `bot.log` - Основные логи приложения
- `error.log` - Только ошибки

### Резервное копирование

```bash
# Резервное копирование базы данных
docker exec deadline_bot sqlite3 /app/data/deadlines.db ".backup /app/data/backup_$(date +%Y%m%d_%H%M%S).db"

# Или через volume
cp data/deadlines.db data/backup_$(date +%Y%m%d_%H%M%S).db
```

## Безопасность

### Переменные окружения

Никогда не храните секреты в коде! Используйте:

1. **Локально**: Файл `.env`
2. **CI/CD**: Secrets в GitHub Actions
3. **Production**: Environment variables платформы

### Секреты GitHub Actions

В репозитории настройте следующие секреты:
- `TELEGRAM_BOT_TOKEN`
- `YONOTE_API_KEY`
- `YONOTE_CALENDAR_ID`
- `DOCKER_HUB_USERNAME`
- `DOCKER_HUB_TOKEN`

## Troubleshooting

### Проблемы с Docker

```bash
# Очистка
docker-compose down
docker system prune -a

# Пересборка
docker-compose build --no-cache
docker-compose up -d
```

### Проблемы с базой данных

```bash
# Проверка БД
docker exec -it deadline_bot sqlite3 data/deadlines.db ".tables"

# Ремиграция
docker exec deadline_bot python scripts/init_db.py
```

### Проблемы с Telegram Bot

1. Проверьте токен в `.env`
2. Убедитесь, что бот добавлен в канал/группу
3. Проверьте логи на ошибки API

## Производительность

### Оптимизация Docker

- Используйте multi-stage builds (уже реализовано)
- Настройте правильные limits для CPU/памяти
- Используйте volumes для персистентных данных

### Масштабирование

- Для высокой нагрузки рассмотрите PostgreSQL вместо SQLite
- Используйте Redis для кеширования
- Настройте load balancer для нескольких инстансов

## Контакты и поддержка

При проблемах:
1. Проверьте логи приложения
2. Используйте health check эндпоинты
3. Создайте issue в репозитории с подробным описанием проблемы

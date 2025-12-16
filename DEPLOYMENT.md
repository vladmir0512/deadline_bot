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

### Вариант 1: Railway (Рекомендуется для быстрого старта)

Railway - современная платформа, которая автоматически обнаруживает ваше приложение и разворачивает его в облаке.

#### ШАГ 1: Подготовка репозитория

Убедитесь, что ваш код уже в GitHub репозитории и содержит:
- `Dockerfile`
- `requirements.txt`
- Переменные окружения настроены

#### ШАГ 2: Регистрация и создание проекта

1. **Зарегистрируйтесь на Railway**: https://railway.app
2. **Создайте новый проект**:
   - Нажмите "New Project"
   - Выберите "Deploy from GitHub repo"
   - Подключите ваш GitHub аккаунт
   - Выберите репозиторий `deadline_bot`

#### ШАГ 3: Настройка переменных окружения

В Railway dashboard откройте ваш проект и перейдите в раздел **"Variables"**:

```env
# Обязательные переменные
TELEGRAM_BOT_TOKEN=ваш_токен_бота
YONOTE_API_KEY=ваш_api_ключ_yonote
YONOTE_CALENDAR_ID=id_календаря_yonote

# Настройки бота
UPDATE_INTERVAL_MINUTES=30
TELEGRAM_ADMIN_IDS=ваш_telegram_id

# Логирование
LOG_LEVEL=INFO

# Health check
HEALTH_CHECK_PORT=8080
HEALTH_CHECK_HOST=0.0.0.0
```

#### ШАГ 4: Добавление базы данных

Railway предоставляет встроенную PostgreSQL базу данных:

1. В dashboard нажмите **"Add Plugin"**
2. Выберите **"PostgreSQL"**
3. База данных автоматически создастся и привяжется к вашему приложению
4. Railway автоматически добавит переменную `DATABASE_URL` в окружение

#### ШАГ 5: Настройка Volume для данных

Если вы используете SQLite (опционально, Railway рекомендует PostgreSQL):

1. В разделе **"Settings"** → **"Volumes"**
2. Создайте volume с путем `/app/data`
3. Railway автоматически смонтирует его

#### ШАГ 6: Deploy и проверка

1. **Автоматический деплой**: Railway автоматически соберет Docker образ и запустит приложение
2. **Проверка логов**: В разделе "Deployments" посмотрите логи сборки и запуска
3. **Health check**: Перейдите в раздел "Settings" → "Networking" и найдите сгенерированный URL
4. **Тестирование**: Добавьте URL + `/health` для проверки статуса

#### ШАГ 7: Настройка домена (опционально)

1. В разделе **"Settings"** → **"Networking"**
2. Добавьте свой домен
3. Railway предоставит SSL сертификат автоматически

#### Преимущества Railway:

✅ **Автоматическое обнаружение** приложения
✅ **Встроенная PostgreSQL** база данных
✅ **Автоматическое масштабирование**
✅ **SSL сертификаты** бесплатно
✅ **Простой интерфейс** управления
✅ **Интеграция с GitHub** - автоматический деплой при push

#### Возможные проблемы и решения:

**Проблема**: Railway не может найти Dockerfile
**Решение**: Убедитесь, что Dockerfile в корне репозитория

**Проблема**: Переменные окружения не работают
**Решение**: Проверьте названия переменных в Railway dashboard

**Проблема**: База данных не подключается
**Решение**: Используйте встроенную PostgreSQL от Railway вместо SQLite

#### Стоимость:
- **Starter план**: $5/месяц (1GB RAM, 1 CPU)
- **Hobby план**: $10/месяц (4GB RAM, 2 CPU)
- **Pro план**: От $25/месяц (масштабируемые ресурсы)

**Подробное руководство**: [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md)

⚠️ **Railway недоступен в РФ?** → **[RUSSIAN_DEPLOYMENT.md](RUSSIAN_DEPLOYMENT.md)**

Railway идеально подходит для первого развертывания и тестирования в production!

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

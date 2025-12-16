# Пошаговое развертывание Deadline Bot на Ubuntu Server

## 📋 Предварительные требования

### Системные требования:
- **Ubuntu Server** 20.04 LTS или новее
- **RAM**: Минимум 1GB, рекомендуется 2GB+
- **Disk**: Минимум 5GB свободного места
- **CPU**: 1 ядро (можно shared)
- **Network**: Стабильный интернет

### Что понадобится:
- Доступ к серверу по SSH (root или sudo пользователь)
- Доменное имя (опционально, для HTTPS)
- Telegram Bot Token
- Yonote API credentials
- GitHub аккаунт (для CI/CD)

---

## 🚀 ШАГ 1: Подготовка сервера

### 1.1 Обновление системы
```bash
# Подключитесь к серверу
ssh user@your-server-ip

# Обновите систему
sudo apt update && sudo apt upgrade -y

# Установите базовые утилиты
sudo apt install -y curl wget git htop nano ufw
```

### 1.2 Настройка firewall (UFW)
```bash
# Включите UFW
sudo ufw enable

# Разрешите SSH (ваш текущий порт)
sudo ufw allow ssh
sudo ufw allow 22

# Разрешите HTTP/HTTPS (если будете использовать веб-интерфейс)
sudo ufw allow 80
sudo ufw allow 443

# Проверьте статус
sudo ufw status
```

### 1.3 Создание пользователя для бота
```bash
# Создайте пользователя без shell доступа
sudo useradd --system --shell /bin/false --home /opt/deadline-bot deadline-bot

# Создайте директорию для проекта
sudo mkdir -p /opt/deadline-bot
sudo chown deadline-bot:deadline-bot /opt/deadline-bot
```

---

## 🐳 ШАГ 2: Установка Docker

### 2.1 Установка Docker Engine
```bash
# Установите зависимости
sudo apt install -y apt-transport-https ca-certificates gnupg lsb-release

# Добавьте Docker GPG ключ
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Добавьте репозиторий
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Установите Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io

# Запустите Docker
sudo systemctl start docker
sudo systemctl enable docker
```

### 2.2 Установка Docker Compose
```bash
# Скачайте последнюю версию
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Сделайте исполняемым
sudo chmod +x /usr/local/bin/docker-compose

# Проверьте установку
docker --version
docker-compose --version
```

### 2.3 Настройка Docker для пользователя
```bash
# Добавьте пользователя в группу docker
sudo usermod -aG docker $USER

# Перезагрузитесь или выполните:
newgrp docker

# Проверьте работу без sudo
docker run hello-world
```

---

## 📥 ШАГ 3: Развертывание проекта

### 3.1 Клонирование репозитория
```bash
# Перейдите в директорию проекта
cd /opt/deadline-bot

# Клонируйте репозиторий
git clone https://github.com/your-username/deadline_bot.git .

# Или если приватный репозиторий:
git clone https://your-token@github.com/your-username/deadline_bot.git .
```

### 3.2 Создание структуры директорий
```bash
# Создайте необходимые директории
mkdir -p data logs

# Установите правильные права
sudo chown -R deadline-bot:deadline-bot /opt/deadline-bot
```

---

## 🔐 ШАГ 4: Настройка переменных окружения

### 4.1 Создание .env файла
```bash
# Создайте .env файл
nano .env
```

**Содержимое .env файла:**
```env
# Telegram Bot
TELEGRAM_BOT_TOKEN=ваш_токен_бота_здесь

# Yonote API
YONOTE_API_KEY=ваш_ключ_api_здесь
YONOTE_CALENDAR_ID=id_календаря_здесь
YONOTE_TIMEZONE=Europe/Moscow

# База данных
DATABASE_URL=sqlite:///data/deadlines.db

# Настройки бота
UPDATE_INTERVAL_MINUTES=30
TELEGRAM_ADMIN_IDS=ваш_telegram_id_здесь

# Логирование
LOG_LEVEL=INFO

# Health check
HEALTH_CHECK_PORT=8080
HEALTH_CHECK_HOST=0.0.0.0
```

### 4.2 Защита .env файла
```bash
# Установите restrictive права
chmod 600 .env

# Проверьте, что файл не доступен другим
ls -la .env
```

### 4.3 Получение необходимых токенов

#### Telegram Bot Token:
1. Напишите [@BotFather](https://t.me/botfather) в Telegram
2. `/newbot`
3. Следуйте инструкциям
4. Сохраните токен в .env

#### Yonote API:
1. Зайдите в настройки Yonote
2. Сгенерируйте API ключ
3. Получите Calendar ID из URL календаря
4. Добавьте в .env

---

## 🚀 ШАГ 5: Первый запуск

### 5.1 Тестовый запуск
```bash
# Проверьте конфигурацию
docker-compose config

# Соберите образы
docker-compose build

# Запустите в фоновом режиме
docker-compose up -d
```

### 5.2 Проверка запуска
```bash
# Проверьте статус контейнеров
docker-compose ps

# Посмотрите логи
docker-compose logs -f

# Проверьте health check
curl http://localhost:8080/health
```

### 5.3 Тестирование бота
```bash
# Напишите боту /start в Telegram
# Проверьте логи на ошибки
docker-compose logs --tail=50 deadline-bot
```

---

## 🔍 ШАГ 6: Мониторинг и обслуживание

### 6.1 Настройка автоматического перезапуска
```bash
# Docker Compose уже настроен на restart: unless-stopped
# Проверьте настройки в docker-compose.yml
```

### 6.2 Настройка logrotate для логов
```bash
# Создайте конфигурацию logrotate
sudo nano /etc/logrotate.d/deadline-bot

# Содержимое:
/opt/deadline-bot/logs/*.log {
    daily
    missingok
    rotate 7
    compress
    notifempty
    create 644 deadline-bot deadline-bot
}
```

### 6.3 Настройка мониторинга (опционально)

#### Prometheus + Grafana:
```bash
# Установите Prometheus
sudo apt install -y prometheus

# Настройте scrape config для health check
sudo nano /etc/prometheus/prometheus.yml

# Добавьте:
scrape_configs:
  - job_name: 'deadline-bot'
    static_configs:
      - targets: ['localhost:8080']
```

---

## 🔒 ШАГ 7: Безопасность

### 7.1 Настройка SSH
```bash
# Отключите root login
sudo nano /etc/ssh/sshd_config

# Измените:
PermitRootLogin no
PasswordAuthentication no  # Если используете ключи

# Перезагрузите SSH
sudo systemctl reload ssh
```

### 7.2 Настройка fail2ban
```bash
# Установите fail2ban
sudo apt install -y fail2ban

# Создайте jail для SSH
sudo nano /etc/fail2ban/jail.local

# Содержимое:
[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600
```

### 7.3 SSL сертификат (Let's Encrypt)
```bash
# Установите certbot
sudo apt install -y certbot

# Получите сертификат (если есть домен)
sudo certbot certonly --standalone -d your-domain.com

# Настройте nginx для HTTPS (если используете веб-интерфейс)
```

---

## 🔄 ШАГ 8: Резервное копирование

### 8.1 Скрипт резервного копирования
```bash
# Создайте скрипт
sudo nano /opt/deadline-bot/backup.sh

# Содержимое:
#!/bin/bash
BACKUP_DIR="/opt/deadline-bot/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Остановите контейнеры
docker-compose down

# Создайте бэкап БД
cp data/deadlines.db $BACKUP_DIR/deadlines_$DATE.db

# Запустите контейнеры обратно
docker-compose up -d

# Очистите старые бэкапы (старше 7 дней)
find $BACKUP_DIR -name "*.db" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR/deadlines_$DATE.db"
```

### 8.2 Настройка cron для автоматического бэкапа
```bash
# Сделайте скрипт исполняемым
sudo chmod +x /opt/deadline-bot/backup.sh

# Добавьте в crontab (ежедневно в 2:00)
sudo crontab -e

# Добавьте строку:
0 2 * * * /opt/deadline-bot/backup.sh
```

---

## 📈 ШАГ 9: Масштабирование и оптимизация

### 9.1 Настройка Nginx (reverse proxy)
```bash
# Установите nginx
sudo apt install -y nginx

# Создайте конфигурацию
sudo nano /etc/nginx/sites-available/deadline-bot

# Содержимое:
server {
    listen 80;
    server_name your-domain.com;

    location /health {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Другие location блоки по необходимости
}

# Включите сайт
sudo ln -s /etc/nginx/sites-available/deadline-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 9.2 Настройка systemd для управления Docker
```bash
# Создайте systemd unit
sudo nano /etc/systemd/system/deadline-bot.service

# Содержимое:
[Unit]
Description=Deadline Bot Docker Container
After=docker.service network.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/deadline-bot
User=deadline-bot
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
ExecReload=/usr/bin/docker-compose restart

[Install]
WantedBy=multi-user.target

# Включите сервис
sudo systemctl enable deadline-bot
```

---

## 🔄 ШАГ 10: Обновление

### 10.1 Обновление через Git
```bash
cd /opt/deadline-bot

# Получите обновления
git pull origin main

# Пересоберите и перезапустите
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Проверьте логи
docker-compose logs --tail=20
```

### 10.2 Rollback при проблемах
```bash
# Если что-то пошло не так
docker-compose down

# Вернитесь к предыдущему коммиту
git checkout HEAD~1

# Перезапустите
docker-compose up -d
```

---

## 🚨 ШАГ 11: Troubleshooting

### 11.1 Проверка состояния
```bash
# Статус всех компонентов
docker-compose ps

# Логи всех сервисов
docker-compose logs

# Health check
curl -f http://localhost:8080/health || echo "Health check failed"

# Использование ресурсов
docker stats
```

### 11.2 Распространенные проблемы

#### Контейнер не запускается:
```bash
# Проверьте логи детально
docker-compose logs deadline-bot

# Проверьте переменные окружения
docker-compose exec deadline-bot env
```

#### База данных повреждена:
```bash
# Восстановите из бэкапа
cp backups/deadlines_latest.db data/deadlines.db
docker-compose restart
```

#### Недостаточно места:
```bash
# Очистите Docker
docker system prune -a

# Проверьте использование диска
df -h
```

---

## 📊 ШАГ 12: Финальная проверка

### 12.1 Полный checklist
- [ ] Сервер обновлен
- [ ] Docker установлен и работает
- [ ] Проект склонирован
- [ ] .env настроен с правильными секретами
- [ ] Контейнеры запущены
- [ ] Health check возвращает "healthy"
- [ ] Бот отвечает в Telegram
- [ ] Логи не содержат ошибок
- [ ] Firewall настроен
- [ ] Резервное копирование работает
- [ ] Мониторинг настроен

### 12.2 Команды для ежедневного мониторинга
```bash
# Проверка статуса
docker-compose ps
curl -s http://localhost:8080/health | jq .status

# Просмотр логов
docker-compose logs --tail=20 -f

# Проверка использования ресурсов
docker stats --no-stream
```

---

## 🎯 Итого

После выполнения всех шагов у вас будет:
- ✅ Полностью рабочий Deadline Bot
- ✅ Автоматический перезапуск при падении
- ✅ Мониторинг здоровья системы
- ✅ Резервное копирование
- ✅ Безопасная конфигурация
- ✅ Возможность легкого обновления

**Время на развертывание: 1-2 часа**

**Стоимость: Бесплатно (кроме VPS)**

При возникновении проблем проверяйте логи и health check статус!

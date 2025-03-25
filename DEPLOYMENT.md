# Инструкция по развертыванию на Hostinger

Это пошаговая инструкция по развертыванию образовательного веб-приложения на хостинге Hostinger с использованием MySQL.

## Предварительные требования

1. Аккаунт на Hostinger с хостинг-планом
2. Доменное имя (настроенное на Hostinger)
3. SSH-доступ к серверу
4. Базовые знания командной строки Linux

## Шаг 1: Подготовка локального проекта

Перед загрузкой на сервер убедитесь, что вы выполнили следующие шаги:

1. Обновите файл `.env` с реальными данными:
   ```
   SECRET_KEY=<ваш_секретный_ключ>
   DEBUG=False
   ALLOWED_HOSTS=your-domain.com,www.your-domain.com
   
   DB_ENGINE=django.db.backends.mysql
   DB_NAME=<имя_базы_данных>
   DB_USER=<имя_пользователя_базы_данных>
   DB_PASSWORD=<пароль_базы_данных>
   DB_HOST=localhost
   DB_PORT=3306
   ```

2. Проверьте, что все необходимые пакеты указаны в `requirements.txt`

## Шаг 2: Создание базы данных MySQL на Hostinger

1. Войдите в панель управления Hostinger
2. Перейдите в раздел "Базы данных" или "MySQL Databases"
3. Создайте новую базу данных MySQL:
   - Введите имя базы данных (например, `u24689363_okucenter_db`)
   - Создайте пользователя базы данных (например, `u24689363_orynbekdulatkg`)
   - Задайте надежный пароль
   - Нажмите "Создать"
4. Запишите данные для подключения (имя базы данных, имя пользователя, пароль)

## Шаг 3: Настройка сервера на Hostinger

### Подключение к серверу

```bash
ssh u123456@your-server-ip
```

### Установка необходимых пакетов

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv nginx git
```

## Шаг 4: Загрузка проекта на сервер

### Клонирование репозитория или загрузка файлов

Если вы используете Git:
```bash
mkdir -p ~/projects
cd ~/projects
git clone <url_вашего_репозитория> okucenter
cd okucenter
```

Или загрузите файлы через SFTP/SCP.

### Настройка виртуального окружения

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Настройка переменных окружения

Создайте файл `.env` на сервере с теми же настройками, что и в локальном проекте, но с актуальными данными для сервера.

## Шаг 5: Миграция данных

### Выполнение миграций

```bash
python manage.py migrate
```

### Миграция данных из SQLite (если необходимо)

Если у вас есть данные в SQLite, которые нужно перенести:

1. Загрузите файл SQLite на сервер
2. Запустите скрипт миграции:
   ```bash
   python migrate_to_postgres.py
   ```

### Сбор статических файлов

```bash
python collect_static.py
```

## Шаг 6: Настройка Gunicorn

### Создание службы systemd для Gunicorn

Создайте файл `/etc/systemd/system/okucenter.service`:

```ini
[Unit]
Description=Gunicorn daemon for OkuCenter
After=network.target

[Service]
User=u123456
Group=u123456
WorkingDirectory=/home/u123456/projects/okucenter
ExecStart=/home/u123456/projects/okucenter/venv/bin/gunicorn -c gunicorn_config.py okucenter.wsgi:application
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Запуск и включение службы

```bash
sudo systemctl start okucenter
sudo systemctl enable okucenter
sudo systemctl status okucenter
```

## Шаг 7: Настройка Nginx

### Создание конфигурации Nginx

Создайте файл `/etc/nginx/sites-available/okucenter`:

```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        alias /home/u123456/projects/okucenter/staticfiles/;
    }
    
    location /media/ {
        alias /home/u123456/projects/okucenter/media/;
    }
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Активация конфигурации Nginx

```bash
sudo ln -s /etc/nginx/sites-available/okucenter /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Шаг 8: Настройка SSL с Let's Encrypt

### Установка Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### Получение SSL-сертификата

```bash
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

## Шаг 9: Настройка резервного копирования

### Создание скрипта для резервного копирования

Создайте файл `~/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/home/u123456/backups"
DATE=$(date +%Y%m%d-%H%M%S)
DB_NAME="your_db_name"
DB_USER="your_db_username"
DB_PASSWORD="your_db_password"

# Создание директории для бэкапов
mkdir -p $BACKUP_DIR

# Бэкап базы данных
mysqldump -u $DB_USER -p$DB_PASSWORD $DB_NAME > $BACKUP_DIR/db_backup_$DATE.sql

# Бэкап медиа-файлов
tar -czf $BACKUP_DIR/media_backup_$DATE.tar.gz -C /home/u123456/projects/okucenter media

# Удаление старых бэкапов (старше 30 дней)
find $BACKUP_DIR -name "db_backup_*" -type f -mtime +30 -delete
find $BACKUP_DIR -name "media_backup_*" -type f -mtime +30 -delete
```

### Настройка автоматического резервного копирования через cron

```bash
chmod +x ~/backup.sh
crontab -e
```

Добавьте строку для запуска скрипта каждый день в 3:00:
```
0 3 * * * /home/u123456/backup.sh
```

## Шаг 10: Мониторинг и обслуживание

### Проверка логов

```bash
# Логи Django/Gunicorn
tail -f /home/u123456/projects/okucenter/logs/gunicorn_error.log

# Логи Nginx
sudo tail -f /var/log/nginx/error.log
```

### Перезапуск служб при необходимости

```bash
sudo systemctl restart okucenter
sudo systemctl restart nginx
```

## Шаг 11: Обновление приложения

Для обновления приложения выполните следующие шаги:

1. Обновите код:
   ```bash
   cd ~/projects/okucenter
   git pull  # если используете Git
   ```

2. Установите новые зависимости:
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Выполните миграции:
   ```bash
   python manage.py migrate
   ```

4. Соберите статические файлы:
   ```bash
   python collect_static.py
   ```

5. Перезапустите Gunicorn:
   ```bash
   sudo systemctl restart okucenter
   ```

## Устранение неполадок

### Проблемы с подключением к базе данных

1. Проверьте настройки в файле `.env`
2. Убедитесь, что MySQL запущен и доступен
3. Проверьте права доступа пользователя базы данных

### Проблемы с Gunicorn

1. Проверьте логи: `tail -f logs/gunicorn_error.log`
2. Проверьте статус службы: `sudo systemctl status okucenter`
3. Проверьте конфигурацию в `gunicorn_config.py`

### Проблемы с Nginx

1. Проверьте логи: `sudo tail -f /var/log/nginx/error.log`
2. Проверьте конфигурацию: `sudo nginx -t`
3. Проверьте статус службы: `sudo systemctl status nginx`

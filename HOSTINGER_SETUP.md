# Пошаговая инструкция по развертыванию на Hostinger

## Шаг 1: Подготовка файлов для загрузки

1. Убедитесь, что в файле `.env` указаны правильные настройки:
   - Правильное имя базы данных: `u24689283_load_okucenter`
   - Правильное имя пользователя: `u24689283_dulat_orynbek`
   - Правильный пароль от базы данных
   - Правильные домены в ALLOWED_HOSTS: `aqylgym.com,www.aqylgym.com`

2. Создайте архив проекта для загрузки:
   - Включите все файлы проекта, кроме виртуального окружения (venv)
   - Включите файлы `.env`, `requirements.txt`, `gunicorn_config.py`

## Шаг 2: Загрузка файлов на Hostinger

1. Войдите в панель управления Hostinger
2. Перейдите в File Manager или используйте FTP-клиент
3. Загрузите архив в корневую директорию вашего сайта (обычно это `/public_html/`)
4. Распакуйте архив

## Шаг 3: Настройка Python и виртуального окружения

1. Подключитесь к серверу через SSH:
   ```
   ssh u24689283@aqylgym.com
   ```

2. Перейдите в директорию проекта:
   ```
   cd /public_html/
   ```

3. Создайте виртуальное окружение:
   ```
   python3 -m venv venv
   ```

4. Активируйте виртуальное окружение:
   ```
   source venv/bin/activate
   ```

5. Установите зависимости:
   ```
   pip install -r requirements.txt
   ```

## Шаг 4: Настройка базы данных и статических файлов

1. Выполните миграции:
   ```
   python manage.py migrate
   ```

2. Если у вас есть данные в SQLite, которые нужно перенести:
   ```
   python migrate_to_mysql.py
   ```

3. Соберите статические файлы:
   ```
   python manage.py collectstatic --noinput
   ```

## Шаг 5: Настройка Gunicorn

1. Создайте файл конфигурации для запуска через Supervisor (если поддерживается Hostinger):
   ```
   nano /home/u24689283/.config/supervisor/okucenter.conf
   ```

2. Добавьте следующее содержимое:
   ```
   [program:okucenter]
   command=/home/u24689283/public_html/venv/bin/gunicorn -c gunicorn_config.py okucenter.wsgi:application
   directory=/home/u24689283/public_html
   user=u24689283
   autostart=true
   autorestart=true
   redirect_stderr=true
   stdout_logfile=/home/u24689283/public_html/logs/gunicorn.log
   ```

3. Перезапустите Supervisor:
   ```
   supervisorctl reread
   supervisorctl update
   supervisorctl restart okucenter
   ```

## Шаг 6: Настройка Nginx (если доступно)

Если у вас есть доступ к настройке Nginx, создайте конфигурационный файл:

```
server {
    listen 80;
    server_name aqylgym.com www.aqylgym.com;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        alias /home/u24689283/public_html/staticfiles/;
    }
    
    location /media/ {
        alias /home/u24689283/public_html/media/;
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

## Шаг 7: Настройка .htaccess (если Nginx недоступен)

Если у вас нет доступа к Nginx, создайте файл `.htaccess` в корневой директории:

```
RewriteEngine On
RewriteCond %{REQUEST_URI} !^/static/
RewriteCond %{REQUEST_URI} !^/media/
RewriteRule ^(.*)$ http://127.0.0.1:8000/$1 [P,L]
```

## Шаг 8: Проверка работоспособности

1. Откройте ваш сайт в браузере: `https://aqylgym.com`
2. Проверьте логи на наличие ошибок:
   ```
   tail -f logs/gunicorn.log
   ```

## Шаг 9: Настройка резервного копирования

1. Создайте скрипт для резервного копирования:
   ```
   nano ~/backup.sh
   ```

2. Добавьте следующее содержимое:
   ```bash
   #!/bin/bash
   BACKUP_DIR="/home/u24689283/backups"
   DATE=$(date +%Y%m%d-%H%M%S)
   DB_NAME="u24689283_load_okucenter"
   DB_USER="u24689283_dulat_orynbek"
   DB_PASSWORD="your_db_password"

   # Создание директории для бэкапов
   mkdir -p $BACKUP_DIR

   # Бэкап базы данных
   mysqldump -u $DB_USER -p$DB_PASSWORD $DB_NAME > $BACKUP_DIR/db_backup_$DATE.sql

   # Бэкап медиа-файлов
   tar -czf $BACKUP_DIR/media_backup_$DATE.tar.gz -C /home/u24689283/public_html media

   # Удаление старых бэкапов (старше 30 дней)
   find $BACKUP_DIR -name "db_backup_*" -type f -mtime +30 -delete
   find $BACKUP_DIR -name "media_backup_*" -type f -mtime +30 -delete
   ```

3. Сделайте скрипт исполняемым:
   ```
   chmod +x ~/backup.sh
   ```

4. Настройте cron для автоматического резервного копирования:
   ```
   crontab -e
   ```

5. Добавьте строку для запуска скрипта каждый день в 3:00:
   ```
   0 3 * * * /home/u24689283/backup.sh
   ```

## Устранение неполадок

### Проблемы с подключением к базе данных

1. Проверьте настройки в файле `.env`
2. Убедитесь, что MySQL запущен и доступен
3. Проверьте права доступа пользователя базы данных

### Проблемы с Gunicorn

1. Проверьте логи: `tail -f logs/gunicorn.log`
2. Проверьте статус Supervisor: `supervisorctl status okucenter`
3. Проверьте конфигурацию в `gunicorn_config.py`

### Проблемы с доступом к сайту

1. Проверьте настройки DNS для вашего домена
2. Проверьте настройки Nginx или .htaccess
3. Проверьте, что Gunicorn запущен и работает на порту 8000

# Инструкция по деплою образовательного центра на Railway

Railway - это современная платформа для хостинга приложений, которая предлагает простой способ развертывания Django-приложений с интеграцией баз данных и других сервисов.

## Подготовка проекта

1. Мы уже подготовили необходимые файлы для деплоя:
   - `Procfile` - инструкции для запуска приложения
   - `runtime.txt` - версия Python
   - `railway.json` - конфигурация Railway
   - Обновленный `requirements.txt` с необходимыми зависимостями
   - Обновленный `settings.py` с поддержкой Railway

2. Запустите скрипт подготовки проекта:
   ```
   python prepare_for_railway.py
   ```

## Настройка Railway

1. Создайте аккаунт на [Railway.app](https://railway.app/) (если еще не создали)

2. Установите Railway CLI:
   ```
   npm i -g @railway/cli
   ```

3. Войдите в аккаунт Railway:
   ```
   railway login
   ```

4. Инициализируйте проект в текущей директории:
   ```
   railway init
   ```
   - Выберите опцию "Empty Project" для создания нового проекта

5. Добавьте базу данных PostgreSQL:
   ```
   railway add
   ```
   - Выберите "PostgreSQL" из списка сервисов

## Настройка переменных окружения

Настройте необходимые переменные окружения через веб-интерфейс Railway или с помощью CLI:

```
railway variables set SECRET_KEY=ваш_секретный_ключ
railway variables set DEBUG=False
railway variables set ALLOWED_HOSTS=.railway.app,aqylgym.com,www.aqylgym.com
```

## Деплой приложения

1. Выполните деплой:
   ```
   railway up
   ```

2. После успешного деплоя откройте ваше приложение:
   ```
   railway open
   ```

## Миграция данных из локальной базы в Railway

Если у вас есть существующие данные в локальной базе данных SQLite или MySQL, вы можете перенести их в PostgreSQL на Railway.

### Экспорт данных из локальной базы

1. Создайте дамп данных:
   ```
   python manage.py dumpdata --exclude auth.permission --exclude contenttypes > data_dump.json
   ```

### Импорт данных в Railway

1. Получите URL для подключения к базе данных PostgreSQL на Railway:
   ```
   railway variables get DATABASE_URL
   ```

2. Создайте временный файл `.env.railway` с переменной `DATABASE_URL` из предыдущего шага

3. Загрузите данные в базу данных Railway:
   ```
   DATABASE_URL=$(railway variables get DATABASE_URL) python manage.py loaddata data_dump.json
   ```

## Создание суперпользователя

Создайте суперпользователя для доступа к административной панели:

```
DATABASE_URL=$(railway variables get DATABASE_URL) python manage.py createsuperuser
```

## Настройка домена (опционально)

Если у вас есть собственный домен (например, aqylgym.com):

1. В веб-интерфейсе Railway перейдите в настройки проекта
2. Выберите вкладку "Settings" и найдите раздел "Domains"
3. Добавьте ваш домен и следуйте инструкциям по настройке DNS

## Мониторинг и обслуживание

- Просмотр логов:
  ```
  railway logs
  ```

- Перезапуск приложения:
  ```
  railway service restart
  ```

- Обновление приложения (после внесения изменений):
  ```
  git add .
  git commit -m "Обновление приложения"
  railway up
  ```

## Резервное копирование базы данных

Railway автоматически создает резервные копии базы данных PostgreSQL, но вы также можете создавать их вручную:

```
pg_dump $(railway variables get DATABASE_URL) > backup_$(date +%Y%m%d).sql
```

## Устранение неполадок

Если возникают проблемы с деплоем:

1. Проверьте логи приложения:
   ```
   railway logs
   ```

2. Убедитесь, что все необходимые переменные окружения настроены правильно:
   ```
   railway variables list
   ```

3. Проверьте статус сервисов:
   ```
   railway status
   ```

4. Если проблема связана с базой данных, проверьте подключение:
   ```
   railway connect
   ```

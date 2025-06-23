# Instagram AI Chatbot

Простой чатбот для Instagram, использующий OpenAI API для генерации ответов на сообщения клиентов.

## Структура проекта

- `app.py` - Основной файл приложения
- `instagram_webhook.py` - Обработчик вебхуков Instagram
- `database.py` - Модель базы данных и функции для работы с историей сообщений
- `openai_client.py` - Интеграция с OpenAI API
- `systemprompt.txt` - Системный промпт для OpenAI
- `.env` - Файл с переменными окружения (API ключи и настройки)
- `requirements.txt` - Зависимости проекта

## Требуемые API ключи и настройки

В файле `.env` необходимо указать следующие параметры:

```
OPENAI_API_KEY=your_openai_api_key_here
INSTAGRAM_APP_ID=your_instagram_app_id_here
INSTAGRAM_APP_SECRET=your_instagram_app_secret_here
INSTAGRAM_VERIFY_TOKEN=your_custom_verify_token_here
DATABASE_URL=sqlite:///chatbot.db
PORT=3000
```

## Установка и запуск

1. Установите зависимости:
```
pip install -r requirements.txt
```

2. Запустите приложение:
```
python app.py
```

## Как это работает

1. Когда пользователь отправляет сообщение в Instagram, Instagram отправляет вебхук на ваш сервер.
2. Сервер сохраняет сообщение в базе данных.
3. Сервер получает историю последних 10 сообщений пользователя и 10 ответов бота.
4. Сервер отправляет системный промпт + историю сообщений в OpenAI API.
5. Полученный ответ от OpenAI сохраняется в базе данных и отправляется пользователю.

## Настройка вебхука Instagram

Для настройки вебхука Instagram необходимо:

1. Создать приложение в [Meta for Developers](https://developers.facebook.com/)
2. Добавить продукт "Messenger" в приложение
3. Настроить вебхук для получения сообщений
4. Указать URL вашего сервера в формате `https://your-server.com/webhook`
5. Указать токен верификации (INSTAGRAM_VERIFY_TOKEN из файла .env)
6. Подписаться на события `messages` и `messaging_postbacks`

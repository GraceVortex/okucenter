import os
import requests
import logging
import json
from django.conf import settings

logger = logging.getLogger(__name__)

# Получение настроек Telegram API из переменных окружения
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def send_telegram_message(chat_id, text, parse_mode='HTML', reply_markup=None, media_url=None, media_type=None):
    """
    Отправляет сообщение через Telegram Bot API.
    
    Args:
        chat_id (str): ID чата получателя
        text (str): Текст сообщения
        parse_mode (str, optional): Режим форматирования текста (HTML, Markdown)
        reply_markup (dict, optional): Кнопки для сообщения
        media_url (str, optional): URL медиа-файла
        media_type (str, optional): Тип медиа (photo, video, audio, document)
    
    Returns:
        dict: Результат отправки сообщения
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.error("Telegram Bot Token не настроен")
        return {
            'success': False,
            'error': 'Telegram Bot Token не настроен',
            'message_id': None
        }
    
    # Определяем метод API в зависимости от наличия медиа
    method = 'sendMessage'
    params = {
        'chat_id': chat_id,
        'parse_mode': parse_mode
    }
    
    # Если есть медиа, меняем метод и параметры
    if media_url and media_type:
        if media_type == 'photo':
            method = 'sendPhoto'
            params['photo'] = media_url
            params['caption'] = text
        elif media_type == 'video':
            method = 'sendVideo'
            params['video'] = media_url
            params['caption'] = text
        elif media_type == 'audio':
            method = 'sendAudio'
            params['audio'] = media_url
            params['caption'] = text
        elif media_type == 'document':
            method = 'sendDocument'
            params['document'] = media_url
            params['caption'] = text
    else:
        params['text'] = text
    
    # Добавляем кнопки, если они есть
    if reply_markup:
        params['reply_markup'] = json.dumps(reply_markup)
    
    # Формируем URL запроса
    url = f"{TELEGRAM_API_URL}/{method}"
    
    try:
        # Отправляем запрос к Telegram API
        response = requests.post(url, params=params)
        response_data = response.json()
        
        # Логирование ответа
        logger.info(f"Telegram API ответ: {response_data}")
        
        # Проверка успешности отправки
        if response.status_code == 200 and response_data.get('ok'):
            message_id = response_data.get('result', {}).get('message_id')
            return {
                'success': True,
                'message_id': message_id,
                'response': response_data
            }
        else:
            error_message = response_data.get('description', 'Неизвестная ошибка')
            logger.error(f"Ошибка отправки Telegram: {error_message}")
            return {
                'success': False,
                'error': error_message,
                'response': response_data,
                'message_id': None
            }
    except Exception as e:
        logger.exception(f"Исключение при отправке Telegram сообщения: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'message_id': None
        }

def create_inline_keyboard(buttons):
    """
    Создает встроенную клавиатуру для Telegram сообщения.
    
    Args:
        buttons (list): Список кнопок в формате [{"text": "Текст", "callback_data": "data"}]
    
    Returns:
        dict: Объект reply_markup для Telegram API
    """
    keyboard = []
    row = []
    
    for i, button in enumerate(buttons):
        # Добавляем по 2 кнопки в ряд
        row.append(button)
        if len(row) == 2 or i == len(buttons) - 1:
            keyboard.append(row)
            row = []
    
    return {
        'inline_keyboard': keyboard
    }

def create_reply_keyboard(buttons, one_time=True, resize=True):
    """
    Создает обычную клавиатуру для Telegram сообщения.
    
    Args:
        buttons (list): Список кнопок в формате ["Текст1", "Текст2"]
        one_time (bool): Скрывать клавиатуру после нажатия
        resize (bool): Подгонять размер клавиатуры под экран
    
    Returns:
        dict: Объект reply_markup для Telegram API
    """
    keyboard = []
    row = []
    
    for i, button_text in enumerate(buttons):
        # Добавляем по 2 кнопки в ряд
        row.append({"text": button_text})
        if len(row) == 2 or i == len(buttons) - 1:
            keyboard.append(row)
            row = []
    
    return {
        'keyboard': keyboard,
        'one_time_keyboard': one_time,
        'resize_keyboard': resize
    }

def get_file_url(file_id):
    """
    Получает URL файла по его ID в Telegram.
    
    Args:
        file_id (str): ID файла в Telegram
    
    Returns:
        str: URL файла
    """
    url = f"{TELEGRAM_API_URL}/getFile"
    params = {'file_id': file_id}
    
    try:
        response = requests.get(url, params=params)
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get('ok'):
            file_path = response_data.get('result', {}).get('file_path')
            if file_path:
                return f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        
        return None
    except Exception as e:
        logger.exception(f"Ошибка при получении URL файла: {str(e)}")
        return None

def get_media_type(file_extension):
    """
    Определяет тип медиа-файла по его расширению.
    
    Args:
        file_extension (str): Расширение файла (без точки)
    
    Returns:
        str: Тип медиа для Telegram API
    """
    image_extensions = ['jpg', 'jpeg', 'png', 'gif']
    video_extensions = ['mp4', 'mov', '3gp']
    audio_extensions = ['mp3', 'ogg', 'wav']
    document_extensions = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt']
    
    file_extension = file_extension.lower()
    
    if file_extension in image_extensions:
        return 'photo'
    elif file_extension in video_extensions:
        return 'video'
    elif file_extension in audio_extensions:
        return 'audio'
    elif file_extension in document_extensions:
        return 'document'
    else:
        return 'document'  # По умолчанию считаем документом

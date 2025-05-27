import os
import requests
import logging
import json
from django.conf import settings

logger = logging.getLogger(__name__)

# Получение настроек WhatsApp API из переменных окружения
WHATSAPP_API_URL = os.environ.get('WHATSAPP_API_URL', 'https://graph.facebook.com/v18.0')
WHATSAPP_API_TOKEN = os.environ.get('WHATSAPP_API_TOKEN', '')
WHATSAPP_PHONE_ID = os.environ.get('WHATSAPP_PHONE_ID', '')

def send_whatsapp_message(phone_number, message_text, media_url=None, media_type=None):
    """
    Отправляет сообщение через WhatsApp API.
    
    Args:
        phone_number (str): Номер телефона получателя в формате 7XXXXXXXXXX
        message_text (str): Текст сообщения
        media_url (str, optional): URL медиа-файла
        media_type (str, optional): Тип медиа (image, video, audio, document)
    
    Returns:
        dict: Результат отправки сообщения
    """
    if not WHATSAPP_API_TOKEN:
        logger.error("WhatsApp API токен не настроен")
        return {
            'success': False,
            'error': 'WhatsApp API токен не настроен',
            'message_id': None
        }
    
    if not WHATSAPP_PHONE_ID:
        logger.error("WhatsApp Phone ID не настроен")
        return {
            'success': False,
            'error': 'WhatsApp Phone ID не настроен',
            'message_id': None
        }
    
    # Форматирование номера телефона
    if phone_number.startswith('+'):
        phone_number = phone_number[1:]
    
    # Базовый URL для отправки сообщений
    url = f"{WHATSAPP_API_URL}/{WHATSAPP_PHONE_ID}/messages"
    
    # Заголовки запроса
    headers = {
        'Authorization': f'Bearer {WHATSAPP_API_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    # Базовая структура данных запроса
    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_number,
        "type": "text" if not media_url else media_type
    }
    
    # Добавление текста сообщения или медиа-файла
    if media_url and media_type:
        if media_type == "image":
            data["image"] = {"link": media_url, "caption": message_text}
        elif media_type == "video":
            data["video"] = {"link": media_url, "caption": message_text}
        elif media_type == "audio":
            data["audio"] = {"link": media_url}
        elif media_type == "document":
            data["document"] = {"link": media_url, "caption": message_text}
    else:
        data["text"] = {"body": message_text}
    
    try:
        # Отправка запроса к WhatsApp API
        response = requests.post(url, headers=headers, json=data)
        response_data = response.json()
        
        # Логирование ответа
        logger.info(f"WhatsApp API ответ: {response_data}")
        
        # Проверка успешности отправки
        if response.status_code == 200 and 'messages' in response_data and len(response_data['messages']) > 0:
            message_id = response_data['messages'][0]['id']
            return {
                'success': True,
                'message_id': message_id,
                'response': response_data
            }
        else:
            error_message = response_data.get('error', {}).get('message', 'Неизвестная ошибка')
            logger.error(f"Ошибка отправки WhatsApp: {error_message}")
            return {
                'success': False,
                'error': error_message,
                'response': response_data,
                'message_id': None
            }
    except Exception as e:
        logger.exception(f"Исключение при отправке WhatsApp сообщения: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'message_id': None
        }

def check_message_status(message_id):
    """
    Проверяет статус отправленного сообщения.
    
    Args:
        message_id (str): ID сообщения, полученный при отправке
    
    Returns:
        dict: Статус сообщения
    """
    if not WHATSAPP_API_TOKEN:
        logger.error("WhatsApp API токен не настроен")
        return {
            'success': False,
            'error': 'WhatsApp API токен не настроен'
        }
    
    url = f"{WHATSAPP_API_URL}/{message_id}"
    
    headers = {
        'Authorization': f'Bearer {WHATSAPP_API_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response_data = response.json()
        
        if response.status_code == 200:
            return {
                'success': True,
                'status': response_data.get('status', 'unknown'),
                'response': response_data
            }
        else:
            error_message = response_data.get('error', {}).get('message', 'Неизвестная ошибка')
            logger.error(f"Ошибка проверки статуса WhatsApp: {error_message}")
            return {
                'success': False,
                'error': error_message,
                'response': response_data
            }
    except Exception as e:
        logger.exception(f"Исключение при проверке статуса WhatsApp сообщения: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def get_media_type(file_extension):
    """
    Определяет тип медиа-файла по его расширению.
    
    Args:
        file_extension (str): Расширение файла (без точки)
    
    Returns:
        str: Тип медиа для WhatsApp API
    """
    image_extensions = ['jpg', 'jpeg', 'png', 'gif']
    video_extensions = ['mp4', 'mov', '3gp']
    audio_extensions = ['mp3', 'ogg', 'wav']
    document_extensions = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt']
    
    file_extension = file_extension.lower()
    
    if file_extension in image_extensions:
        return 'image'
    elif file_extension in video_extensions:
        return 'video'
    elif file_extension in audio_extensions:
        return 'audio'
    elif file_extension in document_extensions:
        return 'document'
    else:
        return 'document'  # По умолчанию считаем документом

import logging
import threading
from django.utils import timezone
from django.conf import settings

from .whatsapp_models import WhatsAppBroadcast
from .whatsapp_views import process_broadcast_async

logger = logging.getLogger(__name__)

def check_scheduled_broadcasts():
    """
    Проверяет и запускает запланированные рассылки WhatsApp.
    Эта функция должна вызываться периодически через планировщик задач.
    """
    try:
        # Получаем все запланированные рассылки, время отправки которых уже наступило
        now = timezone.now()
        scheduled_broadcasts = WhatsAppBroadcast.objects.filter(
            status='scheduled',
            scheduled_at__lte=now
        )
        
        logger.info(f"Найдено {scheduled_broadcasts.count()} запланированных рассылок для отправки")
        
        # Запускаем каждую рассылку
        for broadcast in scheduled_broadcasts:
            try:
                # Меняем статус на "в процессе"
                broadcast.status = 'in_progress'
                broadcast.save()
                
                # Формируем базовый URL для медиа-файлов
                base_url = settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'http://localhost:8000'
                
                # Запускаем отправку в отдельном потоке
                thread = threading.Thread(
                    target=process_broadcast_async,
                    args=(broadcast.id, base_url)
                )
                thread.daemon = True
                thread.start()
                
                logger.info(f"Запущена запланированная рассылка: {broadcast.title} (ID: {broadcast.id})")
            except Exception as e:
                logger.error(f"Ошибка при запуске запланированной рассылки {broadcast.id}: {e}")
                broadcast.status = 'failed'
                broadcast.save()
    
    except Exception as e:
        logger.exception(f"Ошибка при проверке запланированных рассылок: {e}")

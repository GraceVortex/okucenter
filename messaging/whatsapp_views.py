from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
import json
import os
import requests
import logging
import threading
from datetime import datetime, timedelta
from django.conf import settings
from django.core.paginator import Paginator
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from accounts.models import User, Student, Parent
from classes.models import Class, ClassSchedule
from .whatsapp_models import WhatsAppBroadcast, WhatsAppMessage
from .whatsapp_utils import send_whatsapp_message as send_whatsapp_api_message, get_media_type

logger = logging.getLogger(__name__)

@login_required
def whatsapp_dashboard(request):
    """Отображает панель управления рассылками WhatsApp"""
    if not request.user.is_admin:
        messages.error(request, "У вас нет прав для доступа к этой странице")
        return redirect('core:home')
    
    # Получаем все рассылки, созданные пользователем
    broadcasts = WhatsAppBroadcast.objects.filter(created_by=request.user).order_by('-created_at')
    
    # Статистика
    stats = {
        'total': broadcasts.count(),
        'completed': broadcasts.filter(status='completed').count(),
        'in_progress': broadcasts.filter(status='in_progress').count(),
        'scheduled': broadcasts.filter(status='scheduled').count(),
        'draft': broadcasts.filter(status='draft').count(),
        'failed': broadcasts.filter(status='failed').count(),
    }
    
    context = {
        'broadcasts': broadcasts[:10],  # Последние 10 рассылок
        'stats': stats
    }
    
    return render(request, 'messaging/whatsapp_dashboard.html', context)

@login_required
def create_broadcast(request):
    """Создание новой рассылки WhatsApp"""
    if not request.user.is_admin:
        messages.error(request, "У вас нет прав для доступа к этой странице")
        return redirect('core:home')
    
    # Получаем все классы для фильтрации
    classes = Class.objects.all().order_by('name')
    
    # Получаем все расписания
    schedules = ClassSchedule.objects.select_related('class_obj').order_by('day_of_week', 'start_time')
    
    if request.method == 'POST':
        # Получаем данные из формы
        title = request.POST.get('title')
        message = request.POST.get('message')
        recipient_type = request.POST.get('recipient_type')
        target_class_id = request.POST.get('target_class')
        target_schedule_id = request.POST.get('target_schedule')
        target_day = request.POST.get('target_day')
        target_grade = request.POST.get('target_grade')
        scheduled_at = request.POST.get('scheduled_at')
        
        # Проверяем обязательные поля
        if not title or not message or not recipient_type:
            messages.error(request, "Пожалуйста, заполните все обязательные поля")
            return render(request, 'messaging/create_broadcast.html', {
                'classes': classes,
                'schedules': schedules,
                'days_of_week': WhatsAppBroadcast._meta.get_field('target_day').choices
            })
        
        # Создаем новую рассылку
        broadcast = WhatsAppBroadcast(
            title=title,
            message=message,
            recipient_type=recipient_type,
            created_by=request.user,
            status='draft'
        )
        
        # Добавляем фильтр по классу обучения, если он указан
        if target_grade:
            broadcast.target_grade = int(target_grade)
        
        # Устанавливаем фильтры, если они указаны
        if target_class_id:
            broadcast.target_class = get_object_or_404(Class, id=target_class_id)
        
        if target_schedule_id:
            broadcast.target_schedule = get_object_or_404(ClassSchedule, id=target_schedule_id)
        
        if target_day and target_day.isdigit():
            broadcast.target_day = int(target_day)
        
        # Обрабатываем медиа-файл, если он загружен
        if 'media_file' in request.FILES:
            broadcast.media_file = request.FILES['media_file']
        
        # Устанавливаем запланированное время, если указано
        if scheduled_at:
            try:
                broadcast.scheduled_at = timezone.datetime.fromisoformat(scheduled_at)
                broadcast.status = 'scheduled'
            except ValueError:
                messages.warning(request, "Неверный формат времени. Рассылка сохранена как черновик.")
        
        # Сохраняем рассылку
        broadcast.save()
        
        # Получаем список получателей
        recipients = broadcast.get_recipients()
        broadcast.total_recipients = len(recipients)
        broadcast.save()
        
        # Создаем сообщения для каждого получателя
        for recipient in recipients:
            WhatsAppMessage.objects.create(
                broadcast=broadcast,
                recipient_type=recipient['type'],
                recipient_id=recipient['id'],
                recipient_name=recipient['name'],
                recipient_phone=recipient['phone']
            )
        
        messages.success(request, f"Рассылка '{title}' успешно создана")
        
        # Если рассылка должна быть отправлена сразу
        if 'send_now' in request.POST:
            return redirect('messaging:send_broadcast', broadcast_id=broadcast.id)
        
        return redirect('messaging:whatsapp_dashboard')
    
    context = {
        'classes': classes,
        'schedules': schedules,
        'days_of_week': WhatsAppBroadcast._meta.get_field('target_day').choices
    }
    
    return render(request, 'messaging/create_broadcast.html', context)

@login_required
def broadcast_detail(request, broadcast_id):
    """Отображает детали рассылки WhatsApp"""
    if not request.user.is_admin:
        messages.error(request, "У вас нет прав для доступа к этой странице")
        return redirect('core:home')
    
    # Получаем рассылку
    broadcast = get_object_or_404(WhatsAppBroadcast, id=broadcast_id)
    
    # Получаем сообщения рассылки
    whatsapp_messages = broadcast.messages.all()
    
    # Статистика по статусам сообщений
    message_stats = {
        'pending': whatsapp_messages.filter(status='pending').count(),
        'sent': whatsapp_messages.filter(status='sent').count(),
        'delivered': whatsapp_messages.filter(status='delivered').count(),
        'read': whatsapp_messages.filter(status='read').count(),
        'failed': whatsapp_messages.filter(status='failed').count(),
    }
    
    context = {
        'broadcast': broadcast,
        'messages': whatsapp_messages,
        'message_stats': message_stats
    }
    
    return render(request, 'messaging/broadcast_detail.html', context)

def process_broadcast_async(broadcast_id, base_url):
    """
    Асинхронная функция для отправки рассылки WhatsApp в фоновом режиме.
    
    Args:
        broadcast_id (int): ID рассылки
        base_url (str): Базовый URL сайта для формирования полных URL медиа-файлов
    """
    try:
        # Получаем рассылку
        broadcast = WhatsAppBroadcast.objects.get(id=broadcast_id)
        
        # Получаем сообщения для отправки
        pending_messages = broadcast.messages.filter(status='pending')
        
        # Отправляем сообщения через WhatsApp API
        success_count = 0
        fail_count = 0
        
        for message in pending_messages:
            try:
                # Подготавливаем медиа-файл, если он есть
                media_url = None
                media_type = None
                if broadcast.media_file:
                    media_url = f"{base_url}{broadcast.media_file.url}"
                    file_ext = broadcast.media_file.name.split('.')[-1]
                    media_type = get_media_type(file_ext)
                
                # Персонализируем текст сообщения
                personalized_text = broadcast.message
                if '{имя_студента}' in personalized_text and message.student:
                    personalized_text = personalized_text.replace('{имя_студента}', message.student.first_name)
                if '{имя_родителя}' in personalized_text and message.parent:
                    personalized_text = personalized_text.replace('{имя_родителя}', message.parent.first_name)
                if '{класс}' in personalized_text and message.student and message.student.class_obj:
                    personalized_text = personalized_text.replace('{класс}', message.student.class_obj.name)
                
                # Отправляем сообщение через WhatsApp API
                result = send_whatsapp_api_message(
                    phone_number=message.recipient_phone,
                    message_text=personalized_text,
                    media_url=media_url,
                    media_type=media_type
                )
                
                # Обновляем статус сообщения
                if result['success']:
                    message.status = 'sent'
                    message.sent_at = timezone.now()
                    message.whatsapp_message_id = result['message_id']
                    success_count += 1
                else:
                    message.status = 'failed'
                    message.error_message = result.get('error', 'Неизвестная ошибка')
                    fail_count += 1
                
                message.save()
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения WhatsApp: {e}")
                message.status = 'failed'
                message.error_message = str(e)
                message.save()
                fail_count += 1
        
        # Обновляем статистику рассылки
        broadcast.successful_sent = success_count
        broadcast.failed_sent = fail_count
        
        # Если все сообщения отправлены, обновляем статус рассылки
        if pending_messages.count() == success_count + fail_count:
            broadcast.status = 'completed' if fail_count == 0 else 'failed'
        
        broadcast.save()
        
        logger.info(f"Рассылка '{broadcast.title}' завершена: {success_count} успешно, {fail_count} с ошибками")
    
    except Exception as e:
        logger.exception(f"Ошибка при обработке рассылки: {e}")
        try:
            broadcast = WhatsAppBroadcast.objects.get(id=broadcast_id)
            broadcast.status = 'failed'
            broadcast.save()
        except:
            pass

@login_required
def send_broadcast(request, broadcast_id):
    """Отправляет рассылку WhatsApp"""
    if not request.user.is_admin:
        messages.error(request, "У вас нет прав для доступа к этой странице")
        return redirect('core:home')
    
    # Получаем рассылку
    broadcast = get_object_or_404(WhatsAppBroadcast, id=broadcast_id)
    
    # Проверяем, можно ли отправить рассылку
    if broadcast.status not in ['draft', 'scheduled']:
        messages.error(request, f"Рассылка '{broadcast.title}' не может быть отправлена (текущий статус: {broadcast.get_status_display()})")
        return redirect('messaging:broadcast_detail', broadcast_id=broadcast.id)
    
    # Обновляем статус рассылки
    broadcast.status = 'in_progress'
    broadcast.save()
    
    # Запускаем отправку в фоновом режиме
    base_url = f"{request.scheme}://{request.get_host()}"
    thread = threading.Thread(
        target=process_broadcast_async,
        args=(broadcast_id, base_url)
    )
    thread.daemon = True
    thread.start()
    
    messages.success(request, f"Рассылка '{broadcast.title}' запущена в фоновом режиме. Обновите страницу через некоторое время, чтобы увидеть результаты.")
    return redirect('messaging:broadcast_detail', broadcast_id=broadcast.id)

@login_required
def cancel_broadcast(request, broadcast_id):
    """Отменяет запланированную рассылку WhatsApp"""
    if not request.user.is_admin:
        messages.error(request, "У вас нет прав для доступа к этой странице")
        return redirect('core:home')
    
    # Получаем рассылку
    broadcast = get_object_or_404(WhatsAppBroadcast, id=broadcast_id)
    
    # Проверяем, можно ли отменить рассылку
    if broadcast.status != 'scheduled':
        messages.error(request, f"Рассылка '{broadcast.title}' не может быть отменена (текущий статус: {broadcast.get_status_display()})")
        return redirect('messaging:broadcast_detail', broadcast_id=broadcast.id)
    
    # Отменяем рассылку
    broadcast.status = 'draft'
    broadcast.scheduled_at = None
    broadcast.save()
    
    messages.success(request, f"Рассылка '{broadcast.title}' отменена")
    return redirect('messaging:broadcast_detail', broadcast_id=broadcast.id)

@login_required
def delete_broadcast(request, broadcast_id):
    """Удаляет рассылку WhatsApp"""
    if not request.user.is_admin:
        messages.error(request, "У вас нет прав для доступа к этой странице")
        return redirect('core:home')
    
    # Получаем рассылку
    broadcast = get_object_or_404(WhatsAppBroadcast, id=broadcast_id)
    
    # Удаляем рассылку
    broadcast.delete()
    
    messages.success(request, f"Рассылка '{broadcast.title}' удалена")
    return redirect('messaging:whatsapp_dashboard')

@login_required
def api_get_recipients(request):
    """API для получения списка получателей на основе фильтров"""
    if not request.user.is_admin:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)
    
    # Получаем параметры фильтрации
    target_class_id = request.GET.get('target_class')
    target_schedule_id = request.GET.get('target_schedule')
    target_day = request.GET.get('target_day')
    target_grade = request.GET.get('target_grade')
    recipient_type = request.GET.get('recipient_type', 'parents')
    
    # Создаем временный объект рассылки для использования метода get_recipients
    broadcast = WhatsAppBroadcast(
        recipient_type=recipient_type,
        created_by=request.user
    )
    
    # Устанавливаем фильтры, если они указаны
    if target_class_id:
        try:
            broadcast.target_class = Class.objects.get(id=target_class_id)
        except Class.DoesNotExist:
            pass
    
    if target_schedule_id:
        try:
            broadcast.target_schedule = ClassSchedule.objects.get(id=target_schedule_id)
        except ClassSchedule.DoesNotExist:
            pass
    
    if target_day and target_day.isdigit():
        broadcast.target_day = int(target_day)
    
    # Устанавливаем фильтр по классу обучения, если он указан
    if target_grade and target_grade.isdigit():
        broadcast.target_grade = int(target_grade)
    
    # Получаем список получателей
    recipients = broadcast.get_recipients()
    
    return JsonResponse({
        'success': True,
        'recipients': recipients,
        'count': len(recipients)
    })

@login_required
@csrf_exempt
def api_get_schedules(request):
    """API для получения расписаний для выбранного класса"""
    if not request.user.is_admin:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)
    
    # Получаем ID класса
    class_id = request.GET.get('class_id')
    
    if not class_id:
        return JsonResponse({'error': 'Не указан ID класса'}, status=400)
    
    # Получаем расписания для выбранного класса
    try:
        schedules = ClassSchedule.objects.filter(class_obj_id=class_id).order_by('day_of_week', 'start_time')
        
        # Форматируем расписания для ответа
        schedules_data = []
        for schedule in schedules:
            day_name = schedule.get_day_of_week_display()
            start_time = schedule.start_time.strftime('%H:%M')
            end_time = schedule.end_time.strftime('%H:%M')
            
            schedules_data.append({
                'id': schedule.id,
                'day': schedule.day_of_week,
                'day_name': day_name,
                'start_time': start_time,
                'end_time': end_time,
                'display_name': f"{day_name}, {start_time}-{end_time}"
            })
        
        return JsonResponse({
            'success': True,
            'schedules': schedules_data
        })
    except Exception as e:
        logger.error(f"Ошибка при получении расписаний: {e}")
        return JsonResponse({'error': str(e)}, status=500)

def send_whatsapp_message(phone, text, media_url=None):
    """
    Отправляет сообщение через WhatsApp API
    
    Args:
        phone (str): Номер телефона получателя в формате 7XXXXXXXXXX
        text (str): Текст сообщения
        media_url (str, optional): URL медиа-файла для отправки
    
    Returns:
        tuple: (success, message_id, error_message)
    """
    # Проверяем, что номер телефона в правильном формате
    if not phone.startswith('+'):
        phone = '+' + phone
    
    # Проверяем, что номер телефона содержит только цифры и знак +
    if not all(c.isdigit() or c == '+' for c in phone):
        return False, None, "Неверный формат номера телефона"
    
    try:
        # Получаем настройки WhatsApp API из переменных окружения
        api_url = os.environ.get('WHATSAPP_API_URL', 'https://api.whatsapp.com/v1/messages')
        api_token = os.environ.get('WHATSAPP_API_TOKEN')
        
        if not api_token:
            logger.error("Отсутствует токен WhatsApp API")
            return False, None, "Отсутствует токен WhatsApp API"
        
        # Формируем данные запроса
        headers = {
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': phone,
            'type': 'text',
            'text': {
                'body': text
            }
        }
        
        # Если есть медиа-файл, изменяем тип сообщения
        if media_url:
            # Определяем тип медиа-файла по расширению
            media_type = 'document'  # по умолчанию
            if media_url.lower().endswith(('.jpg', '.jpeg', '.png')):
                media_type = 'image'
            elif media_url.lower().endswith(('.mp4', '.mov')):
                media_type = 'video'
            elif media_url.lower().endswith(('.mp3', '.ogg', '.wav')):
                media_type = 'audio'
            
            payload['type'] = media_type
            payload[media_type] = {
                'link': media_url
            }
            # Если это документ, добавляем текст как caption
            if media_type == 'document':
                payload[media_type]['caption'] = text
        
        # Отправляем запрос к WhatsApp API
        response = requests.post(api_url, headers=headers, json=payload)
        
        # Проверяем ответ
        if response.status_code == 200:
            response_data = response.json()
            message_id = response_data.get('messages', [{}])[0].get('id')
            return True, message_id, None
        else:
            error_message = f"Ошибка API WhatsApp: {response.status_code} - {response.text}"
            logger.error(error_message)
            return False, None, error_message
    
    except Exception as e:
        error_message = f"Ошибка при отправке сообщения WhatsApp: {str(e)}"
        logger.error(error_message)
        return False, None, error_message

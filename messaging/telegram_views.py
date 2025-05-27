import os
import json
import logging
import threading
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from .telegram_models import TelegramBroadcast, TelegramMessage, TelegramUser
from .telegram_utils import send_telegram_message, get_media_type, create_inline_keyboard
from classes.models import Class, ClassSchedule
from accounts.models import Student, Parent, Teacher

logger = logging.getLogger(__name__)

@login_required
def telegram_dashboard(request):
    """Отображает панель управления рассылками Telegram"""
    if not request.user.is_admin:
        messages.error(request, "У вас нет прав для доступа к этой странице")
        return redirect('core:home')
    
    # Получаем все рассылки, созданные пользователем
    broadcasts = TelegramBroadcast.objects.filter(created_by=request.user).order_by('-created_at')
    
    # Статистика
    stats = {
        'total': broadcasts.count(),
        'completed': broadcasts.filter(status='completed').count(),
        'in_progress': broadcasts.filter(status='in_progress').count(),
        'scheduled': broadcasts.filter(status='scheduled').count(),
        'draft': broadcasts.filter(status='draft').count(),
        'failed': broadcasts.filter(status='failed').count(),
    }
    
    # Статистика по Telegram пользователям
    telegram_stats = {
        'total_users': TelegramUser.objects.filter(is_active=True).count(),
        'students': TelegramUser.objects.filter(role='student', is_active=True).count(),
        'parents': TelegramUser.objects.filter(role='parent', is_active=True).count(),
        'teachers': TelegramUser.objects.filter(role='teacher', is_active=True).count(),
    }
    
    context = {
        'broadcasts': broadcasts[:10],  # Последние 10 рассылок
        'stats': stats,
        'telegram_stats': telegram_stats
    }
    
    return render(request, 'messaging/telegram_dashboard.html', context)

@login_required
def create_telegram_broadcast(request):
    """Создание новой рассылки Telegram"""
    if not request.user.is_admin:
        messages.error(request, "У вас нет прав для доступа к этой странице")
        return redirect('core:home')
    
    # Получаем все классы для фильтрации
    classes = Class.objects.all().order_by('name')
    
    # Получаем все расписания
    schedules = ClassSchedule.objects.select_related('class_obj').order_by('day_of_week', 'start_time')
    
    # Получаем дни недели из модели ClassSchedule
    days_of_week = ClassSchedule._meta.get_field('day_of_week').choices
    
    if request.method == 'POST':
        # Получаем данные из формы
        title = request.POST.get('title')
        message = request.POST.get('message')
        recipient_type = request.POST.get('recipient_type')
        target_class_id = request.POST.get('target_class')
        target_schedule_id = request.POST.get('target_schedule')
        target_day = request.POST.get('target_day')
        scheduled_at = request.POST.get('scheduled_at')
        has_buttons = 'has_buttons' in request.POST
        
        # Проверяем обязательные поля
        if not title or not message or not recipient_type:
            messages.error(request, "Пожалуйста, заполните все обязательные поля")
            return render(request, 'messaging/create_telegram_broadcast.html', {
                'classes': classes,
                'schedules': schedules,
                'days_of_week': days_of_week
            })
        
        # Создаем новую рассылку
        broadcast = TelegramBroadcast(
            title=title,
            message=message,
            recipient_type=recipient_type,
            created_by=request.user,
            status='draft',
            has_buttons=has_buttons
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
        
        # Обрабатываем кнопки, если они есть
        if has_buttons:
            buttons = []
            button_texts = request.POST.getlist('button_text')
            button_data = request.POST.getlist('button_data')
            
            for i in range(len(button_texts)):
                if i < len(button_data) and button_texts[i].strip():
                    buttons.append({
                        "text": button_texts[i].strip(),
                        "callback_data": button_data[i].strip() or button_texts[i].strip()
                    })
            
            if buttons:
                broadcast.buttons_json = json.dumps(buttons)
        
        # Обрабатываем медиа-файл, если он загружен
        if 'media_file' in request.FILES:
            media_file = request.FILES['media_file']
            broadcast.media_file = media_file
            file_ext = media_file.name.split('.')[-1]
            broadcast.media_type = get_media_type(file_ext)
        
        # Обрабатываем запланированное время отправки
        if scheduled_at:
            try:
                broadcast.scheduled_at = datetime.strptime(scheduled_at, '%Y-%m-%d %H:%M')
                broadcast.status = 'scheduled'
            except ValueError:
                messages.error(request, "Неверный формат даты и времени")
                return render(request, 'messaging/create_telegram_broadcast.html', {
                    'classes': classes,
                    'schedules': schedules,
                    'days_of_week': days_of_week
                })
        
        # Сохраняем рассылку
        broadcast.save()
        
        # Получаем список получателей и создаем сообщения
        recipients = broadcast.get_recipients()
        broadcast.total_recipients = len(recipients)
        broadcast.save()
        
        # Создаем сообщения для каждого получателя
        for recipient_data in recipients:
            recipient_id = recipient_data['id']
            recipient_type = recipient_data['type']
            
            try:
                recipient = TelegramUser.objects.get(telegram_id=recipient_id)
                
                # Создаем сообщение
                message = TelegramMessage(
                    broadcast=broadcast,
                    recipient=recipient,
                    recipient_type=recipient_type,
                    status='pending'
                )
                
                # Устанавливаем связи со студентом или родителем
                if recipient_type == 'student' and recipient.student:
                    message.student = recipient.student
                elif recipient_type == 'parent' and recipient.parent:
                    message.parent = recipient.parent
                
                message.save()
            except TelegramUser.DoesNotExist:
                logger.warning(f"Пользователь Telegram с ID {recipient_id} не найден")
        
        # Если нажата кнопка "Отправить сейчас", отправляем рассылку
        if 'send_now' in request.POST:
            broadcast.status = 'in_progress'
            broadcast.save()
            
            # Запускаем отправку в фоновом режиме
            base_url = f"{request.scheme}://{request.get_host()}"
            thread = threading.Thread(
                target=process_telegram_broadcast_async,
                args=(broadcast.id, base_url)
            )
            thread.daemon = True
            thread.start()
            
            messages.success(request, f"Рассылка '{broadcast.title}' запущена в фоновом режиме")
            return redirect('messaging:telegram_broadcast_detail', broadcast_id=broadcast.id)
        
        messages.success(request, f"Рассылка '{broadcast.title}' создана")
        return redirect('messaging:telegram_dashboard')
    
    context = {
        'classes': classes,
        'schedules': schedules,
        'days_of_week': days_of_week
    }
    
    return render(request, 'messaging/create_telegram_broadcast.html', context)

@login_required
def telegram_broadcast_detail(request, broadcast_id):
    """Отображает детали рассылки Telegram"""
    if not request.user.is_admin:
        messages.error(request, "У вас нет прав для доступа к этой странице")
        return redirect('core:home')
    
    # Получаем рассылку
    broadcast = get_object_or_404(TelegramBroadcast, id=broadcast_id)
    
    # Получаем сообщения рассылки с пагинацией
    messages_list = broadcast.messages.all().order_by('-created_at')
    paginator = Paginator(messages_list, 50)  # По 50 сообщений на страницу
    
    page = request.GET.get('page')
    messages_page = paginator.get_page(page)
    
    # Статистика по статусам сообщений
    message_stats = {
        'pending': broadcast.messages.filter(status='pending').count(),
        'sent': broadcast.messages.filter(status='sent').count(),
        'delivered': broadcast.messages.filter(status='delivered').count(),
        'read': broadcast.messages.filter(status='read').count(),
        'failed': broadcast.messages.filter(status='failed').count(),
    }
    
    # Парсим JSON кнопок, если они есть
    buttons = []
    if broadcast.has_buttons and broadcast.buttons_json:
        try:
            buttons = json.loads(broadcast.buttons_json)
        except json.JSONDecodeError:
            logger.error(f"Ошибка при парсинге JSON кнопок для рассылки {broadcast_id}")
    
    context = {
        'broadcast': broadcast,
        'messages': messages_page,
        'message_stats': message_stats,
        'buttons': buttons
    }
    
    return render(request, 'messaging/telegram_broadcast_detail.html', context)

@login_required
def send_telegram_broadcast(request, broadcast_id):
    """Отправляет рассылку Telegram"""
    if not request.user.is_admin:
        messages.error(request, "У вас нет прав для доступа к этой странице")
        return redirect('core:home')
    
    # Получаем рассылку
    broadcast = get_object_or_404(TelegramBroadcast, id=broadcast_id)
    
    # Проверяем, можно ли отправить рассылку
    if broadcast.status not in ['draft', 'scheduled']:
        messages.error(request, f"Рассылка '{broadcast.title}' не может быть отправлена (текущий статус: {broadcast.get_status_display()})")
        return redirect('messaging:telegram_broadcast_detail', broadcast_id=broadcast.id)
    
    # Обновляем статус рассылки
    broadcast.status = 'in_progress'
    broadcast.save()
    
    # Запускаем отправку в фоновом режиме
    base_url = f"{request.scheme}://{request.get_host()}"
    thread = threading.Thread(
        target=process_telegram_broadcast_async,
        args=(broadcast_id, base_url)
    )
    thread.daemon = True
    thread.start()
    
    messages.success(request, f"Рассылка '{broadcast.title}' запущена в фоновом режиме. Обновите страницу через некоторое время, чтобы увидеть результаты.")
    return redirect('messaging:telegram_broadcast_detail', broadcast_id=broadcast.id)

@login_required
def cancel_telegram_broadcast(request, broadcast_id):
    """Отменяет запланированную рассылку Telegram"""
    if not request.user.is_admin:
        messages.error(request, "У вас нет прав для доступа к этой странице")
        return redirect('core:home')
    
    # Получаем рассылку
    broadcast = get_object_or_404(TelegramBroadcast, id=broadcast_id)
    
    # Проверяем, можно ли отменить рассылку
    if broadcast.status != 'scheduled':
        messages.error(request, f"Рассылка '{broadcast.title}' не может быть отменена (текущий статус: {broadcast.get_status_display()})")
        return redirect('messaging:telegram_broadcast_detail', broadcast_id=broadcast.id)
    
    # Обновляем статус рассылки
    broadcast.status = 'draft'
    broadcast.scheduled_at = None
    broadcast.save()
    
    messages.success(request, f"Рассылка '{broadcast.title}' отменена")
    return redirect('messaging:telegram_broadcast_detail', broadcast_id=broadcast.id)

@login_required
def delete_telegram_broadcast(request, broadcast_id):
    """Удаляет рассылку Telegram"""
    if not request.user.is_admin:
        messages.error(request, "У вас нет прав для доступа к этой странице")
        return redirect('core:home')
    
    # Получаем рассылку
    broadcast = get_object_or_404(TelegramBroadcast, id=broadcast_id)
    
    # Удаляем рассылку
    broadcast.delete()
    
    messages.success(request, f"Рассылка '{broadcast.title}' удалена")
    return redirect('messaging:telegram_dashboard')

@login_required
def api_get_telegram_recipients(request):
    """API для получения списка получателей Telegram на основе фильтров"""
    if not request.user.is_admin:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)
    
    # Получаем параметры фильтрации
    target_class_id = request.GET.get('target_class')
    target_schedule_id = request.GET.get('target_schedule')
    target_day = request.GET.get('target_day')
    recipient_type = request.GET.get('recipient_type', 'both')
    
    # Создаем временный объект рассылки для использования метода get_recipients
    broadcast = TelegramBroadcast(
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
    
    # Получаем список получателей
    recipients = broadcast.get_recipients()
    
    return JsonResponse({
        'success': True,
        'recipients': recipients,
        'count': len(recipients)
    })

@login_required
@csrf_exempt
def api_get_telegram_schedules(request):
    """API для получения расписаний для выбранного класса"""
    if not request.user.is_admin:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)
    
    # Получаем ID класса
    class_id = request.GET.get('class_id')
    
    try:
        # Получаем расписания для выбранного класса
        if class_id:
            schedules = ClassSchedule.objects.filter(class_obj_id=class_id).order_by('day_of_week', 'start_time')
        else:
            schedules = ClassSchedule.objects.all().order_by('day_of_week', 'start_time')
        
        # Форматируем данные для ответа
        schedules_data = []
        for schedule in schedules:
            # Получаем название дня недели
            day_name = dict(ClassSchedule._meta.get_field('day_of_week').choices).get(schedule.day_of_week, '')
            
            # Форматируем время
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

def process_telegram_broadcast_async(broadcast_id, base_url):
    """
    Асинхронная функция для отправки рассылки Telegram в фоновом режиме.
    
    Args:
        broadcast_id (int): ID рассылки
        base_url (str): Базовый URL сайта для формирования полных URL медиа-файлов
    """
    try:
        # Получаем рассылку
        broadcast = TelegramBroadcast.objects.get(id=broadcast_id)
        
        # Получаем сообщения для отправки
        pending_messages = broadcast.messages.filter(status='pending')
        
        # Отправляем сообщения через Telegram API
        success_count = 0
        fail_count = 0
        
        # Подготавливаем кнопки, если они есть
        reply_markup = None
        if broadcast.has_buttons and broadcast.buttons_json:
            try:
                buttons = json.loads(broadcast.buttons_json)
                reply_markup = create_inline_keyboard(buttons)
            except json.JSONDecodeError:
                logger.error(f"Ошибка при парсинге JSON кнопок для рассылки {broadcast_id}")
        
        for message in pending_messages:
            try:
                # Подготавливаем медиа-файл, если он есть
                media_url = None
                media_type = None
                if broadcast.media_file:
                    media_url = f"{base_url}{broadcast.media_file.url}"
                    media_type = broadcast.media_type
                
                # Персонализируем текст сообщения
                personalized_text = broadcast.message
                if '{имя}' in personalized_text:
                    personalized_text = personalized_text.replace('{имя}', message.recipient.get_full_name())
                
                if '{имя_студента}' in personalized_text and message.student:
                    personalized_text = personalized_text.replace('{имя_студента}', message.student.get_full_name())
                
                if '{имя_родителя}' in personalized_text and message.parent:
                    personalized_text = personalized_text.replace('{имя_родителя}', message.parent.get_full_name())
                
                if '{класс}' in personalized_text and message.student and message.student.class_obj:
                    personalized_text = personalized_text.replace('{класс}', message.student.class_obj.name)
                
                # Отправляем сообщение через Telegram API
                result = send_telegram_message(
                    chat_id=message.recipient.telegram_id,
                    text=personalized_text,
                    parse_mode='HTML',
                    reply_markup=reply_markup,
                    media_url=media_url,
                    media_type=media_type
                )
                
                # Обновляем статус сообщения
                if result['success']:
                    message.status = 'sent'
                    message.sent_at = timezone.now()
                    message.telegram_message_id = result['message_id']
                    success_count += 1
                else:
                    message.status = 'failed'
                    message.error_message = result.get('error', 'Неизвестная ошибка')
                    fail_count += 1
                
                message.save()
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения Telegram: {e}")
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
            broadcast = TelegramBroadcast.objects.get(id=broadcast_id)
            broadcast.status = 'failed'
            broadcast.save()
        except:
            pass

@login_required
def telegram_users(request):
    """Отображает список пользователей Telegram"""
    if not request.user.is_admin:
        messages.error(request, "У вас нет прав для доступа к этой странице")
        return redirect('core:home')
    
    # Получаем всех пользователей Telegram
    users = TelegramUser.objects.all().order_by('-created_at')
    
    # Фильтрация по роли
    role = request.GET.get('role')
    if role:
        users = users.filter(role=role)
    
    # Фильтрация по активности
    is_active = request.GET.get('is_active')
    if is_active is not None:
        is_active = is_active.lower() == 'true'
        users = users.filter(is_active=is_active)
    
    # Поиск по имени или ID
    search = request.GET.get('search')
    if search:
        users = users.filter(
            Q(telegram_id__icontains=search) |
            Q(username__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(phone__icontains=search)
        )
    
    # Пагинация
    paginator = Paginator(users, 20)  # По 20 пользователей на страницу
    page = request.GET.get('page')
    users_page = paginator.get_page(page)
    
    # Статистика
    stats = {
        'total': TelegramUser.objects.count(),
        'active': TelegramUser.objects.filter(is_active=True).count(),
        'students': TelegramUser.objects.filter(role='student').count(),
        'parents': TelegramUser.objects.filter(role='parent').count(),
        'teachers': TelegramUser.objects.filter(role='teacher').count(),
        'admins': TelegramUser.objects.filter(role='admin').count(),
        'reception': TelegramUser.objects.filter(role='reception').count(),
        'unknown': TelegramUser.objects.filter(role='unknown').count(),
    }
    
    context = {
        'users': users_page,
        'stats': stats,
        'role': role,
        'is_active': is_active,
        'search': search
    }
    
    return render(request, 'messaging/telegram_users.html', context)

@login_required
def toggle_telegram_user(request, user_id):
    """Включает/выключает пользователя Telegram"""
    if not request.user.is_admin:
        messages.error(request, "У вас нет прав для доступа к этой странице")
        return redirect('core:home')
    
    # Получаем пользователя
    user = get_object_or_404(TelegramUser, id=user_id)
    
    # Меняем статус активности
    user.is_active = not user.is_active
    user.save()
    
    messages.success(request, f"Пользователь {user} {'активирован' if user.is_active else 'деактивирован'}")
    return redirect('messaging:telegram_users')

@login_required
def link_telegram_user(request, user_id):
    """Связывает пользователя Telegram с учетной записью в системе"""
    if not request.user.is_admin:
        messages.error(request, "У вас нет прав для доступа к этой странице")
        return redirect('core:home')
    
    # Получаем пользователя Telegram
    user = get_object_or_404(TelegramUser, id=user_id)
    
    if request.method == 'POST':
        role = request.POST.get('role')
        entity_id = request.POST.get('entity_id')
        
        if role and entity_id:
            # Обновляем роль пользователя
            user.role = role
            
            # Связываем с соответствующей сущностью
            if role == 'student':
                try:
                    student = Student.objects.get(id=entity_id)
                    user.student = student
                    user.parent = None
                    messages.success(request, f"Пользователь {user} связан со студентом {student}")
                except Student.DoesNotExist:
                    messages.error(request, "Студент не найден")
            elif role == 'parent':
                try:
                    parent = Parent.objects.get(id=entity_id)
                    user.parent = parent
                    user.student = None
                    messages.success(request, f"Пользователь {user} связан с родителем {parent}")
                except Parent.DoesNotExist:
                    messages.error(request, "Родитель не найден")
            elif role == 'teacher':
                try:
                    teacher = Teacher.objects.get(id=entity_id)
                    user.student = None
                    user.parent = None
                    messages.success(request, f"Пользователь {user} связан с преподавателем {teacher}")
                except Teacher.DoesNotExist:
                    messages.error(request, "Преподаватель не найден")
            else:
                user.student = None
                user.parent = None
                messages.success(request, f"Роль пользователя {user} изменена на {role}")
            
            user.save()
            return redirect('messaging:telegram_users')
    
    # Получаем списки студентов, родителей и преподавателей
    students = Student.objects.all().order_by('last_name', 'first_name')
    parents = Parent.objects.all().order_by('last_name', 'first_name')
    teachers = Teacher.objects.all().order_by('last_name', 'first_name')
    
    context = {
        'telegram_user': user,
        'students': students,
        'parents': parents,
        'teachers': teachers
    }
    
    return render(request, 'messaging/link_telegram_user.html', context)

@login_required
def messaging_choice(request):
    """Отображает страницу выбора между WhatsApp и Telegram рассылками"""
    if not request.user.is_admin:
        messages.error(request, "У вас нет прав для доступа к этой странице")
        return redirect('core:home')
    
    # Статистика по WhatsApp
    whatsapp_stats = {
        'total_broadcasts': 0,
        'total_messages': 0,
        'success_rate': 0
    }
    
    # Статистика по Telegram
    telegram_stats = {
        'total_broadcasts': TelegramBroadcast.objects.count(),
        'total_users': TelegramUser.objects.filter(is_active=True).count(),
        'total_messages': TelegramMessage.objects.count(),
        'success_rate': 0
    }
    
    # Рассчитываем процент успешных отправок для Telegram
    if TelegramMessage.objects.count() > 0:
        success_count = TelegramMessage.objects.filter(status__in=['sent', 'delivered', 'read']).count()
        telegram_stats['success_rate'] = round((success_count / TelegramMessage.objects.count()) * 100)
    
    context = {
        'whatsapp_stats': whatsapp_stats,
        'telegram_stats': telegram_stats
    }
    
    return render(request, 'messaging/messaging_choice.html', context)

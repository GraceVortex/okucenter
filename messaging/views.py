from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.db.models import Q, Count, Max, F, ExpressionWrapper, BooleanField
from django.utils import timezone
from django.contrib import messages
from django.core.paginator import Paginator

from accounts.models import User
from .models import Conversation, Message

@login_required
def inbox(request):
    """Отображает список диалогов пользователя"""
    
    # Получаем все диалоги пользователя
    conversations = Conversation.objects.filter(
        participants=request.user
    ).annotate(
        # Подсчитываем количество непрочитанных сообщений
        unread_count=Count(
            'messages',
            filter=Q(messages__is_read=False) & ~Q(messages__sender=request.user)
        ),
        # Получаем дату последнего сообщения
        last_message_date=Max('messages__created_at'),
        # Получаем последнее сообщение
        last_message=Max('messages__content')
    ).order_by('-last_message_date')
    
    # Получаем список администраторов и ресепшн для создания нового диалога
    if request.user.is_parent:
        admin_users = User.objects.filter(user_type__in=['admin', 'reception'])
    else:
        admin_users = None
    
    context = {
        'conversations': conversations,
        'admin_users': admin_users,
    }
    
    return render(request, 'messaging/inbox.html', context)

@login_required
def conversation_detail(request, conversation_id):
    """Отображает детали диалога и позволяет отправлять сообщения"""
    
    # Получаем диалог и проверяем доступ
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    # Проверяем, является ли пользователь участником диалога
    if request.user not in conversation.participants.all():
        return HttpResponseForbidden("У вас нет доступа к этому диалогу.")
    
    # Отмечаем все сообщения в диалоге как прочитанные для текущего пользователя
    conversation.mark_as_read(request.user)
    
    # Обрабатываем отправку нового сообщения
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        
        if content:
            # Создаем новое сообщение
            message = Message.objects.create(
                conversation=conversation,
                sender=request.user,
                content=content
            )
            
            # Обновляем дату последнего обновления диалога
            conversation.updated_at = timezone.now()
            conversation.save(update_fields=['updated_at'])
            
            # Если диалог был закрыт, открываем его снова
            if conversation.status == 'closed':
                conversation.status = 'active'
                conversation.save(update_fields=['status'])
            
            # Если это AJAX запрос, возвращаем JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'message': {
                        'id': message.id,
                        'content': message.content,
                        'sender': message.sender.get_full_name() or message.sender.username,
                        'created_at': message.created_at.strftime('%d.%m.%Y %H:%M'),
                        'is_own': True
                    }
                })
            
            # Перенаправляем на страницу диалога
            return redirect('messaging:conversation_detail', conversation_id=conversation.id)
    
    # Получаем все сообщения в диалоге
    messages_list = conversation.messages.select_related('sender').order_by('created_at')
    
    # Пагинация сообщений
    paginator = Paginator(messages_list, 50)  # 50 сообщений на страницу
    page = request.GET.get('page', paginator.num_pages)
    messages_page = paginator.get_page(page)
    
    context = {
        'conversation': conversation,
        'messages': messages_page,
    }
    
    return render(request, 'messaging/conversation_detail.html', context)

@login_required
def create_conversation(request):
    """Создает новый диалог"""
    
    # Только родители и администраторы могут создавать диалоги
    if not request.user.user_type in ['parent', 'admin', 'reception']:
        return HttpResponseForbidden("У вас нет доступа к этой функции.")
    
    if request.method == 'POST':
        recipient_id = request.POST.get('recipient')
        subject = request.POST.get('subject', '').strip()
        content = request.POST.get('content', '').strip()
        
        # Проверяем наличие получателя и содержимого
        if not recipient_id or not content:
            messages.error(request, "Необходимо указать получателя и текст сообщения.")
            return redirect('messaging:inbox')
        
        # Получаем получателя
        try:
            recipient = User.objects.get(id=recipient_id)
        except User.DoesNotExist:
            messages.error(request, "Указанный получатель не существует.")
            return redirect('messaging:inbox')
        
        # Проверяем, что родитель может писать только администраторам и ресепшн
        if request.user.is_parent and not recipient.user_type in ['admin', 'reception']:
            return HttpResponseForbidden("Родители могут создавать диалоги только с администрацией.")
        
        # Создаем новый диалог
        conversation = Conversation.objects.create(subject=subject)
        conversation.participants.add(request.user, recipient)
        
        # Создаем первое сообщение
        Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content=content
        )
        
        messages.success(request, "Диалог успешно создан.")
        return redirect('messaging:conversation_detail', conversation_id=conversation.id)
    
    # Получаем список возможных получателей
    if request.user.is_parent:
        recipients = User.objects.filter(user_type__in=['admin', 'reception'])
    elif request.user.is_admin or request.user.is_reception:
        recipients = User.objects.filter(user_type='parent')
    else:
        recipients = User.objects.none()
    
    context = {
        'recipients': recipients,
    }
    
    return render(request, 'messaging/create_conversation.html', context)

@login_required
def close_conversation(request, conversation_id):
    """Закрывает диалог"""
    
    # Получаем диалог и проверяем доступ
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    # Проверяем, является ли пользователь участником диалога
    if request.user not in conversation.participants.all():
        return HttpResponseForbidden("У вас нет доступа к этому диалогу.")
    
    # Только администраторы и ресепшн могут закрывать диалоги
    if not request.user.user_type in ['admin', 'reception']:
        return HttpResponseForbidden("Только администрация может закрывать диалоги.")
    
    # Закрываем диалог
    conversation.status = 'closed'
    conversation.save(update_fields=['status'])
    
    messages.success(request, "Диалог успешно закрыт.")
    return redirect('messaging:inbox')

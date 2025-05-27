import logging
import json
import hmac
import hashlib
import base64
import uuid
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Count, Max
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.core.paginator import Paginator

from .models_integrations import Integration, SocialAccount, Message, Conversation, Webhook, WebhookLog
from .models_new import Contact, Company, Deal
from .forms import WebhookForm

logger = logging.getLogger(__name__)

@login_required
def integration_list(request):
    """
    Отображение списка интеграций
    """
    integrations = Integration.objects.all().order_by('name')
    
    context = {
        'integrations': integrations,
    }
    
    return render(request, 'crm/integration_list.html', context)

@login_required
def integration_detail(request, integration_id):
    """
    Отображение детальной информации об интеграции
    """
    integration = get_object_or_404(Integration, id=integration_id)
    
    # Получаем вебхуки интеграции
    webhooks = integration.webhooks.all()
    
    # Получаем статистику по сообщениям
    messages_stats = {
        'total': integration.messages.count(),
        'incoming': integration.messages.filter(message_type='incoming').count(),
        'outgoing': integration.messages.filter(message_type='outgoing').count(),
        'today': integration.messages.filter(sent_at__date=timezone.now().date()).count(),
        'week': integration.messages.filter(sent_at__gte=timezone.now() - timedelta(days=7)).count(),
        'month': integration.messages.filter(sent_at__gte=timezone.now() - timedelta(days=30)).count(),
    }
    
    context = {
        'integration': integration,
        'webhooks': webhooks,
        'messages_stats': messages_stats,
    }
    
    return render(request, 'crm/integration_detail.html', context)

@login_required
def integration_create(request):
    """
    Создание новой интеграции
    """
    if request.method == 'POST':
        integration_type = request.POST.get('integration_type')
        name = request.POST.get('name')
        
        if not integration_type or not name:
            messages.error(request, 'Необходимо указать тип и название интеграции')
            return redirect('integration_list')
        
        # Создаем базовую интеграцию
        integration = Integration.objects.create(
            name=name,
            integration_type=integration_type,
            created_by=request.user
        )
        
        # Перенаправляем на страницу настройки интеграции
        return redirect('integration_setup', integration_id=integration.id)
    
    # Получаем доступные типы интеграций
    integration_types = Integration.INTEGRATION_TYPE_CHOICES
    
    context = {
        'integration_types': integration_types,
    }
    
    return render(request, 'crm/integration_create.html', context)

@login_required
def integration_setup(request, integration_id):
    """
    Настройка интеграции
    """
    integration = get_object_or_404(Integration, id=integration_id)
    
    if request.method == 'POST':
        # Получаем настройки из POST-запроса
        settings_data = {}
        
        if integration.integration_type == 'whatsapp':
            settings_data['api_key'] = request.POST.get('api_key', '')
            settings_data['phone_number_id'] = request.POST.get('phone_number_id', '')
            settings_data['business_account_id'] = request.POST.get('business_account_id', '')
            settings_data['webhook_verify_token'] = request.POST.get('webhook_verify_token', '')
        
        elif integration.integration_type == 'instagram':
            settings_data['access_token'] = request.POST.get('access_token', '')
            settings_data['instagram_account_id'] = request.POST.get('instagram_account_id', '')
            settings_data['app_id'] = request.POST.get('app_id', '')
            settings_data['app_secret'] = request.POST.get('app_secret', '')
        
        # Сохраняем настройки
        integration.settings = settings_data
        integration.save()
        
        messages.success(request, f'Настройки интеграции "{integration.name}" успешно сохранены')
        return redirect('integration_detail', integration_id=integration.id)
    
    context = {
        'integration': integration,
    }
    
    # Выбираем шаблон в зависимости от типа интеграции
    template_name = f'crm/integration_setup_{integration.integration_type}.html'
    
    return render(request, template_name, context)

@login_required
def webhook_create(request, integration_id):
    """
    Создание нового вебхука для интеграции
    """
    integration = get_object_or_404(Integration, id=integration_id)
    
    if request.method == 'POST':
        form = WebhookForm(request.POST)
        if form.is_valid():
            # Создаем вебхук
            webhook = Webhook.objects.create(
                name=form.cleaned_data['name'],
                url=form.cleaned_data['url'],
                secret_key=form.cleaned_data['secret_key'],
                is_active=form.cleaned_data['is_active'],
                events=form.cleaned_data['events'],
                integration=integration,
                created_by=request.user
            )
            
            messages.success(request, f'Вебхук "{webhook.name}" успешно создан')
            return redirect('integration_detail', integration_id=integration.id)
    else:
        form = WebhookForm()
    
    context = {
        'form': form,
        'integration': integration,
    }
    
    return render(request, 'crm/webhook_form.html', context)

@login_required
def webhook_update(request, webhook_id):
    """
    Обновление существующего вебхука
    """
    webhook = get_object_or_404(Webhook, id=webhook_id)
    
    if request.method == 'POST':
        form = WebhookForm(request.POST)
        if form.is_valid():
            # Обновляем вебхук
            webhook.name = form.cleaned_data['name']
            webhook.url = form.cleaned_data['url']
            webhook.secret_key = form.cleaned_data['secret_key']
            webhook.is_active = form.cleaned_data['is_active']
            webhook.events = form.cleaned_data['events']
            webhook.save()
            
            messages.success(request, f'Вебхук "{webhook.name}" успешно обновлен')
            return redirect('integration_detail', integration_id=webhook.integration.id)
    else:
        initial_data = {
            'name': webhook.name,
            'url': webhook.url,
            'secret_key': webhook.secret_key,
            'is_active': webhook.is_active,
            'events': webhook.events,
        }
        form = WebhookForm(initial=initial_data)
    
    context = {
        'form': form,
        'webhook': webhook,
        'integration': webhook.integration,
    }
    
    return render(request, 'crm/webhook_form.html', context)

@login_required
def conversation_list(request):
    """
    Отображение списка бесед
    """
    # Получаем параметры фильтрации
    channel = request.GET.get('channel', '')
    is_active = request.GET.get('is_active', 'true')
    search_query = request.GET.get('q', '')
    
    # Базовый запрос
    conversations_query = Conversation.objects.all()
    
    # Применяем фильтры
    if channel:
        conversations_query = conversations_query.filter(channel=channel)
    
    if is_active == 'true':
        conversations_query = conversations_query.filter(is_active=True, is_archived=False)
    elif is_active == 'false':
        conversations_query = conversations_query.filter(is_active=False)
    elif is_active == 'archived':
        conversations_query = conversations_query.filter(is_archived=True)
    
    # Применяем поиск
    if search_query:
        conversations_query = conversations_query.filter(
            Q(contact__first_name__icontains=search_query) |
            Q(contact__last_name__icontains=search_query) |
            Q(contact__middle_name__icontains=search_query) |
            Q(contact__phone__icontains=search_query) |
            Q(contact__email__icontains=search_query)
        )
    
    # Добавляем аннотацию с количеством непрочитанных сообщений
    conversations_query = conversations_query.annotate(
        unread_count=Count(
            'contact__messages',
            filter=Q(
                contact__messages__message_type='incoming',
                contact__messages__is_read=False,
                contact__messages__channel=models.F('channel')
            )
        )
    )
    
    # Сортировка
    conversations_query = conversations_query.order_by('-last_message_at')
    
    # Пагинация
    paginator = Paginator(conversations_query, 25)  # 25 бесед на страницу
    page_number = request.GET.get('page', 1)
    conversations = paginator.get_page(page_number)
    
    context = {
        'conversations': conversations,
        'channel': channel,
        'is_active': is_active,
        'search_query': search_query,
        'channel_choices': Message.CHANNEL_CHOICES,
    }
    
    return render(request, 'crm/conversation_list.html', context)

@login_required
def conversation_detail(request, conversation_id):
    """
    Отображение беседы с контактом
    """
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    # Получаем сообщения беседы
    messages_query = Message.objects.filter(
        contact=conversation.contact,
        channel=conversation.channel
    ).order_by('sent_at')
    
    # Отмечаем входящие сообщения как прочитанные
    unread_messages = messages_query.filter(message_type='incoming', is_read=False)
    for message in unread_messages:
        message.is_read = True
        message.read_at = timezone.now()
        message.save()
    
    # Получаем информацию о контакте
    contact = conversation.contact
    
    # Получаем социальные аккаунты контакта
    social_accounts = contact.social_accounts.all()
    
    # Получаем сделки контакта
    deals = contact.deals.all().order_by('-created_at')
    
    context = {
        'conversation': conversation,
        'messages': messages_query,
        'contact': contact,
        'social_accounts': social_accounts,
        'deals': deals,
    }
    
    return render(request, 'crm/conversation_detail.html', context)

@login_required
def send_message(request, conversation_id):
    """
    Отправка сообщения в беседу
    """
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    if request.method == 'POST':
        text = request.POST.get('text', '').strip()
        
        if not text:
            messages.error(request, 'Текст сообщения не может быть пустым')
            return redirect('conversation_detail', conversation_id=conversation.id)
        
        # Создаем исходящее сообщение
        message = Message.objects.create(
            message_type='outgoing',
            channel=conversation.channel,
            text=text,
            contact=conversation.contact,
            integration=Integration.objects.filter(integration_type=conversation.channel).first(),
            sent_at=timezone.now(),
            is_delivered=False
        )
        
        # Обновляем дату последнего сообщения в беседе
        conversation.last_message_at = timezone.now()
        conversation.save()
        
        # Здесь должна быть логика отправки сообщения через API
        # В зависимости от канала (WhatsApp, Instagram и т.д.)
        
        # Для примера просто отмечаем сообщение как доставленное
        message.is_delivered = True
        message.delivered_at = timezone.now()
        message.save()
        
        messages.success(request, 'Сообщение успешно отправлено')
        return redirect('conversation_detail', conversation_id=conversation.id)
    
    return redirect('conversation_detail', conversation_id=conversation.id)

@csrf_exempt
def whatsapp_webhook(request):
    """
    Вебхук для приема сообщений от WhatsApp API
    """
    if request.method == 'GET':
        # Верификация вебхука
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        # Получаем токен верификации из настроек интеграции
        integration = Integration.objects.filter(integration_type='whatsapp').first()
        if not integration:
            return HttpResponse('Integration not found', status=400)
        
        verify_token = integration.settings.get('webhook_verify_token', '')
        
        if mode == 'subscribe' and token == verify_token:
            return HttpResponse(challenge)
        
        return HttpResponse('Verification failed', status=403)
    
    elif request.method == 'POST':
        # Получаем данные из запроса
        try:
            data = json.loads(request.body.decode('utf-8'))
            logger.info(f"WhatsApp webhook received: {data}")
            
            # Проверяем подпись запроса
            integration = Integration.objects.filter(integration_type='whatsapp').first()
            if not integration:
                return HttpResponse('Integration not found', status=400)
            
            # Обрабатываем входящие сообщения
            if 'entry' in data and len(data['entry']) > 0:
                for entry in data['entry']:
                    if 'changes' in entry and len(entry['changes']) > 0:
                        for change in entry['changes']:
                            if change.get('field') == 'messages':
                                value = change.get('value', {})
                                
                                if 'messages' in value and len(value['messages']) > 0:
                                    for message_data in value['messages']:
                                        # Обрабатываем сообщение
                                        process_whatsapp_message(message_data, integration)
            
            return HttpResponse('OK')
        
        except Exception as e:
            logger.error(f"Error processing WhatsApp webhook: {str(e)}")
            return HttpResponse('Error', status=500)
    
    return HttpResponse('Method not allowed', status=405)

def process_whatsapp_message(message_data, integration):
    """
    Обработка входящего сообщения WhatsApp
    """
    try:
        # Получаем данные сообщения
        message_id = message_data.get('id')
        from_number = message_data.get('from')
        timestamp = message_data.get('timestamp')
        
        # Преобразуем timestamp в datetime
        sent_at = datetime.fromtimestamp(int(timestamp) / 1000.0, tz=timezone.utc)
        
        # Получаем текст сообщения
        text = None
        media_url = None
        media_type = None
        
        if 'text' in message_data:
            text = message_data['text'].get('body', '')
        elif 'image' in message_data:
            media_type = 'image'
            media_url = message_data['image'].get('url', '')
        elif 'audio' in message_data:
            media_type = 'audio'
            media_url = message_data['audio'].get('url', '')
        elif 'video' in message_data:
            media_type = 'video'
            media_url = message_data['video'].get('url', '')
        elif 'document' in message_data:
            media_type = 'document'
            media_url = message_data['document'].get('url', '')
        
        # Ищем контакт по номеру телефона
        contact = Contact.objects.filter(phone=from_number).first()
        
        # Если контакт не найден, создаем новый
        if not contact:
            contact = Contact.objects.create(
                first_name='WhatsApp',
                last_name=from_number,
                phone=from_number,
                contact_type='lead'
            )
            
            # Создаем социальный аккаунт для контакта
            SocialAccount.objects.create(
                contact=contact,
                account_type='whatsapp',
                username=from_number,
                account_id=from_number
            )
        
        # Ищем или создаем беседу
        conversation, created = Conversation.objects.get_or_create(
            contact=contact,
            channel='whatsapp',
            defaults={
                'last_message_at': sent_at,
                'is_active': True
            }
        )
        
        # Если беседа не новая, обновляем дату последнего сообщения
        if not created:
            conversation.last_message_at = sent_at
            conversation.is_active = True
            conversation.is_archived = False
            conversation.save()
        
        # Создаем сообщение
        message = Message.objects.create(
            message_id=message_id,
            message_type='incoming',
            channel='whatsapp',
            text=text,
            media_url=media_url,
            media_type=media_type,
            contact=contact,
            integration=integration,
            sent_at=sent_at,
            is_delivered=True,
            delivered_at=sent_at,
            metadata=message_data
        )
        
        logger.info(f"WhatsApp message processed: {message}")
        
        return message
    
    except Exception as e:
        logger.error(f"Error processing WhatsApp message: {str(e)}")
        return None

@csrf_exempt
def instagram_webhook(request):
    """
    Вебхук для приема сообщений от Instagram API
    """
    if request.method == 'GET':
        # Верификация вебхука
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        # Получаем токен верификации из настроек интеграции
        integration = Integration.objects.filter(integration_type='instagram').first()
        if not integration:
            return HttpResponse('Integration not found', status=400)
        
        verify_token = integration.settings.get('webhook_verify_token', '')
        
        if mode == 'subscribe' and token == verify_token:
            return HttpResponse(challenge)
        
        return HttpResponse('Verification failed', status=403)
    
    elif request.method == 'POST':
        # Получаем данные из запроса
        try:
            data = json.loads(request.body.decode('utf-8'))
            logger.info(f"Instagram webhook received: {data}")
            
            # Проверяем подпись запроса
            integration = Integration.objects.filter(integration_type='instagram').first()
            if not integration:
                return HttpResponse('Integration not found', status=400)
            
            # Обрабатываем входящие сообщения
            if 'entry' in data and len(data['entry']) > 0:
                for entry in data['entry']:
                    if 'messaging' in entry and len(entry['messaging']) > 0:
                        for messaging in entry['messaging']:
                            # Обрабатываем сообщение
                            process_instagram_message(messaging, integration)
            
            return HttpResponse('OK')
        
        except Exception as e:
            logger.error(f"Error processing Instagram webhook: {str(e)}")
            return HttpResponse('Error', status=500)
    
    return HttpResponse('Method not allowed', status=405)

def process_instagram_message(messaging_data, integration):
    """
    Обработка входящего сообщения Instagram
    """
    try:
        # Получаем данные сообщения
        sender_id = messaging_data.get('sender', {}).get('id')
        recipient_id = messaging_data.get('recipient', {}).get('id')
        timestamp = messaging_data.get('timestamp')
        
        # Преобразуем timestamp в datetime
        sent_at = datetime.fromtimestamp(int(timestamp) / 1000.0, tz=timezone.utc)
        
        # Получаем текст сообщения
        message_data = messaging_data.get('message', {})
        message_id = message_data.get('mid')
        text = message_data.get('text')
        
        # Получаем данные о медиа
        media_url = None
        media_type = None
        
        if 'attachments' in message_data and len(message_data['attachments']) > 0:
            attachment = message_data['attachments'][0]
            media_type = attachment.get('type')
            
            if media_type == 'image':
                media_url = attachment.get('payload', {}).get('url')
            elif media_type == 'video':
                media_url = attachment.get('payload', {}).get('url')
            elif media_type == 'audio':
                media_url = attachment.get('payload', {}).get('url')
            elif media_type == 'file':
                media_url = attachment.get('payload', {}).get('url')
        
        # Ищем социальный аккаунт по ID
        social_account = SocialAccount.objects.filter(
            account_type='instagram',
            account_id=sender_id
        ).first()
        
        # Если социальный аккаунт найден, используем связанный контакт
        if social_account:
            contact = social_account.contact
        else:
            # Иначе создаем новый контакт и социальный аккаунт
            contact = Contact.objects.create(
                first_name='Instagram',
                last_name=sender_id,
                contact_type='lead'
            )
            
            # Создаем социальный аккаунт для контакта
            SocialAccount.objects.create(
                contact=contact,
                account_type='instagram',
                username=sender_id,
                account_id=sender_id
            )
        
        # Ищем или создаем беседу
        conversation, created = Conversation.objects.get_or_create(
            contact=contact,
            channel='instagram',
            defaults={
                'last_message_at': sent_at,
                'is_active': True
            }
        )
        
        # Если беседа не новая, обновляем дату последнего сообщения
        if not created:
            conversation.last_message_at = sent_at
            conversation.is_active = True
            conversation.is_archived = False
            conversation.save()
        
        # Создаем сообщение
        message = Message.objects.create(
            message_id=message_id,
            message_type='incoming',
            channel='instagram',
            text=text,
            media_url=media_url,
            media_type=media_type,
            contact=contact,
            integration=integration,
            sent_at=sent_at,
            is_delivered=True,
            delivered_at=sent_at,
            metadata=messaging_data
        )
        
        logger.info(f"Instagram message processed: {message}")
        
        return message
    
    except Exception as e:
        logger.error(f"Error processing Instagram message: {str(e)}")
        return None

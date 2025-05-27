import logging
import json
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings
from django.db.models import Q
from .models import Lead, MetaBusinessAccount, SocialMessage
from .views import marketer_required

logger = logging.getLogger(__name__)

@marketer_required
def meta_accounts_list(request):
    """Отображение списка аккаунтов Meta Business"""
    accounts = MetaBusinessAccount.objects.all()
    
    context = {
        'accounts': accounts,
    }
    
    return render(request, 'crm/meta_accounts_list.html', context)

@marketer_required
def meta_account_create(request):
    """Создание нового аккаунта Meta Business"""
    if request.method == 'POST':
        name = request.POST.get('name')
        account_type = request.POST.get('account_type')
        business_id = request.POST.get('business_id')
        phone_number_id = request.POST.get('phone_number_id')
        access_token = request.POST.get('access_token')
        
        if not name or not account_type or not access_token:
            messages.error(request, "Все поля обязательны для заполнения")
            return redirect('crm:meta_account_create')
        
        # Проверка валидности токена через API Meta
        is_valid = validate_meta_token(access_token, account_type, business_id, phone_number_id)
        
        if not is_valid:
            messages.error(request, "Не удалось подтвердить доступ к API Meta. Проверьте введенные данные.")
            return redirect('crm:meta_account_create')
        
        account = MetaBusinessAccount.objects.create(
            name=name,
            account_type=account_type,
            business_id=business_id,
            phone_number_id=phone_number_id,
            access_token=access_token,
            created_by=request.user
        )
        
        messages.success(request, f"Аккаунт '{account.name}' успешно создан")
        return redirect('crm:meta_accounts_list')
    
    context = {
        'account_types': MetaBusinessAccount.ACCOUNT_TYPE_CHOICES,
    }
    
    return render(request, 'crm/meta_account_form.html', context)

@marketer_required
def meta_account_update(request, account_id):
    """Обновление существующего аккаунта Meta Business"""
    account = get_object_or_404(MetaBusinessAccount, id=account_id)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        account_type = request.POST.get('account_type')
        business_id = request.POST.get('business_id')
        phone_number_id = request.POST.get('phone_number_id')
        access_token = request.POST.get('access_token')
        
        if not name or not account_type:
            messages.error(request, "Название и тип аккаунта обязательны для заполнения")
            return redirect('crm:meta_account_update', account_id=account.id)
        
        # Если токен изменился, проверяем его валидность
        if access_token and access_token != account.access_token:
            is_valid = validate_meta_token(access_token, account_type, business_id, phone_number_id)
            
            if not is_valid:
                messages.error(request, "Не удалось подтвердить доступ к API Meta. Проверьте введенные данные.")
                return redirect('crm:meta_account_update', account_id=account.id)
            
            account.access_token = access_token
        
        account.name = name
        account.account_type = account_type
        if business_id:
            account.business_id = business_id
        if phone_number_id:
            account.phone_number_id = phone_number_id
        account.save()
        
        messages.success(request, f"Аккаунт '{account.name}' успешно обновлен")
        return redirect('crm:meta_accounts_list')
    
    context = {
        'account': account,
        'account_types': MetaBusinessAccount.ACCOUNT_TYPE_CHOICES,
    }
    
    return render(request, 'crm/meta_account_form.html', context)

@marketer_required
def send_whatsapp_message(request, lead_id):
    """Отправка сообщения WhatsApp лиду"""
    lead = get_object_or_404(Lead, id=lead_id)
    accounts = MetaBusinessAccount.objects.filter(account_type='whatsapp', is_active=True)
    
    if request.method == 'POST':
        account_id = request.POST.get('account_id')
        message_text = request.POST.get('message_text')
        
        if not account_id or not message_text:
            messages.error(request, "Выберите аккаунт и введите текст сообщения")
            return redirect('crm:send_whatsapp_message', lead_id=lead.id)
        
        account = get_object_or_404(MetaBusinessAccount, id=account_id)
        
        # Форматируем номер телефона для WhatsApp API
        phone_number = lead.phone_number.replace(' ', '').replace('-', '').replace('+', '')
        if phone_number.startswith('8'):
            phone_number = '7' + phone_number[1:]
        
        # Отправляем сообщение через WhatsApp API
        success, response_data = send_whatsapp_api(account, phone_number, message_text)
        
        if success:
            # Создаем запись о сообщении
            message = SocialMessage.objects.create(
                lead=lead,
                account=account,
                message_type='outgoing',
                message_text=message_text,
                message_id=response_data.get('messages', [{}])[0].get('id', ''),
                sent_by=request.user
            )
            
            messages.success(request, "Сообщение успешно отправлено")
            return redirect('crm:lead_detail', lead_id=lead.id)
        else:
            messages.error(request, f"Ошибка при отправке сообщения: {response_data.get('error', {}).get('message', 'Неизвестная ошибка')}")
            return redirect('crm:send_whatsapp_message', lead_id=lead.id)
    
    context = {
        'lead': lead,
        'accounts': accounts,
    }
    
    return render(request, 'crm/send_whatsapp_form.html', context)

@marketer_required
def social_messages(request, lead_id):
    """Отображение истории сообщений для лида"""
    lead = get_object_or_404(Lead, id=lead_id)
    messages_list = SocialMessage.objects.filter(lead=lead).order_by('created_at')
    
    context = {
        'lead': lead,
        'messages_list': messages_list,
    }
    
    return render(request, 'crm/social_messages.html', context)

@csrf_exempt
def webhook_handler(request):
    """Обработчик webhook от Meta для получения входящих сообщений"""
    if request.method == 'GET':
        # Верификация webhook
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        if mode and token:
            if mode == 'subscribe' and token == settings.META_WEBHOOK_VERIFY_TOKEN:
                return JsonResponse({'hub.challenge': challenge}, status=200)
            else:
                return JsonResponse({'error': 'Verification failed'}, status=403)
    
    elif request.method == 'POST':
        # Получение входящих сообщений
        try:
            data = json.loads(request.body.decode('utf-8'))
            logger.info(f"Webhook received: {data}")
            
            # Обработка входящих сообщений WhatsApp
            if 'entry' in data and len(data['entry']) > 0:
                for entry in data['entry']:
                    if 'changes' in entry and len(entry['changes']) > 0:
                        for change in entry['changes']:
                            if change.get('field') == 'messages':
                                process_whatsapp_message(change['value'])
            
            return JsonResponse({'status': 'success'}, status=200)
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

def validate_meta_token(access_token, account_type, business_id=None, phone_number_id=None):
    """Проверка валидности токена через API Meta"""
    try:
        if account_type == 'whatsapp' and phone_number_id:
            # Для WhatsApp проверяем доступ к Phone Number ID
            url = f"https://graph.facebook.com/v17.0/{phone_number_id}"
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            response = requests.get(url, headers=headers)
            return response.status_code == 200
        
        elif account_type == 'instagram' and business_id:
            # Для Instagram проверяем доступ к Business ID
            url = f"https://graph.facebook.com/v17.0/{business_id}"
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            response = requests.get(url, headers=headers)
            return response.status_code == 200
        
        return False
    except Exception as e:
        logger.error(f"Error validating Meta token: {str(e)}")
        return False

def send_whatsapp_api(account, phone_number, message_text):
    """Отправка сообщения через WhatsApp API"""
    try:
        url = f"https://graph.facebook.com/v17.0/{account.phone_number_id}/messages"
        headers = {
            'Authorization': f'Bearer {account.access_token}',
            'Content-Type': 'application/json'
        }
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number,
            "type": "text",
            "text": {
                "body": message_text
            }
        }
        
        response = requests.post(url, headers=headers, json=data)
        response_data = response.json()
        
        if response.status_code == 200:
            return True, response_data
        else:
            logger.error(f"WhatsApp API error: {response_data}")
            return False, response_data
    
    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {str(e)}")
        return False, {"error": {"message": str(e)}}

def process_whatsapp_message(data):
    """Обработка входящего сообщения WhatsApp"""
    try:
        # Получаем данные из webhook
        phone_number_id = data.get('metadata', {}).get('phone_number_id')
        if not phone_number_id:
            logger.error("No phone_number_id in webhook data")
            return
        
        # Находим соответствующий аккаунт
        account = MetaBusinessAccount.objects.filter(
            phone_number_id=phone_number_id,
            account_type='whatsapp',
            is_active=True
        ).first()
        
        if not account:
            logger.error(f"No active WhatsApp account found for phone_number_id: {phone_number_id}")
            return
        
        # Обрабатываем сообщения
        if 'messages' in data and len(data['messages']) > 0:
            for message_data in data['messages']:
                if message_data.get('type') == 'text':
                    # Получаем данные сообщения
                    message_id = message_data.get('id')
                    from_number = message_data.get('from')
                    message_text = message_data.get('text', {}).get('body', '')
                    timestamp = message_data.get('timestamp')
                    
                    # Ищем лида по номеру телефона
                    # Форматируем номер для поиска
                    search_number = from_number
                    if search_number.startswith('7'):
                        search_number = '+7' + search_number[1:]
                    elif search_number.startswith('8'):
                        search_number = '+7' + search_number[1:]
                    
                    lead = Lead.objects.filter(
                        Q(phone_number__contains=search_number[-10:])
                    ).first()
                    
                    if lead:
                        # Создаем запись о входящем сообщении
                        SocialMessage.objects.create(
                            lead=lead,
                            account=account,
                            message_type='incoming',
                            message_text=message_text,
                            message_id=message_id,
                            created_at=timezone.datetime.fromtimestamp(int(timestamp)) if timestamp else timezone.now()
                        )
                        logger.info(f"Incoming WhatsApp message saved for lead: {lead.id}")
                    else:
                        logger.warning(f"No lead found for phone number: {from_number}")
    
    except Exception as e:
        logger.error(f"Error processing WhatsApp message: {str(e)}")

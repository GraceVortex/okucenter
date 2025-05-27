import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from .models import Lead, MetaBusinessAccount, SocialMessage
from .views import marketer_required
from .social_views import send_whatsapp_api

logger = logging.getLogger(__name__)

@marketer_required
def bulk_message_form(request):
    """Форма для массовой рассылки сообщений лидам"""
    # Получаем все активные аккаунты WhatsApp
    whatsapp_accounts = MetaBusinessAccount.objects.filter(
        account_type='whatsapp',
        is_active=True
    )
    
    # Получаем все источники лидов для фильтрации
    lead_sources = Lead.objects.values_list('source__name', flat=True).distinct()
    lead_sources = [source for source in lead_sources if source]
    
    # Получаем все этапы продаж для фильтрации
    sale_stages = Lead.objects.values_list('current_stage__name', flat=True).distinct()
    sale_stages = [stage for stage in sale_stages if stage]
    
    context = {
        'whatsapp_accounts': whatsapp_accounts,
        'lead_sources': lead_sources,
        'sale_stages': sale_stages,
    }
    
    return render(request, 'crm/bulk_message_form.html', context)

@marketer_required
def send_bulk_messages(request):
    """Отправка массовых сообщений лидам"""
    if request.method != 'POST':
        return redirect('crm:bulk_message_form')
    
    # Получаем параметры из формы
    account_id = request.POST.get('account_id')
    message_text = request.POST.get('message_text')
    source_filter = request.POST.get('source_filter')
    stage_filter = request.POST.get('stage_filter')
    status_filter = request.POST.get('status_filter')
    
    if not account_id or not message_text:
        messages.error(request, "Необходимо выбрать аккаунт и ввести текст сообщения")
        return redirect('crm:bulk_message_form')
    
    # Получаем аккаунт WhatsApp
    account = get_object_or_404(MetaBusinessAccount, id=account_id, account_type='whatsapp', is_active=True)
    
    # Базовый запрос для лидов
    leads_query = Lead.objects.filter(phone_number__isnull=False)
    
    # Применяем фильтры
    if source_filter:
        leads_query = leads_query.filter(source__name=source_filter)
    
    if stage_filter:
        leads_query = leads_query.filter(current_stage__name=stage_filter)
    
    if status_filter:
        leads_query = leads_query.filter(status=status_filter)
    
    # Получаем лидов
    leads = leads_query.all()
    
    if not leads:
        messages.warning(request, "Нет лидов, соответствующих выбранным критериям")
        return redirect('crm:bulk_message_form')
    
    # Отправляем сообщения
    success_count = 0
    error_count = 0
    
    for lead in leads:
        # Форматируем номер телефона для WhatsApp API
        phone_number = lead.phone_number.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        if phone_number.startswith('+'):
            phone_number = phone_number[1:]
        elif phone_number.startswith('8'):
            phone_number = '7' + phone_number[1:]
        
        # Отправляем сообщение
        success, response_data = send_whatsapp_api(account, phone_number, message_text)
        
        if success:
            # Создаем запись о сообщении
            SocialMessage.objects.create(
                lead=lead,
                account=account,
                message_type='outgoing',
                message_text=message_text,
                sent_by=request.user
            )
            success_count += 1
        else:
            error_count += 1
            logger.error(f"Error sending message to {lead.full_name} ({lead.phone_number}): {response_data}")
    
    # Выводим сообщение о результатах
    if success_count > 0:
        messages.success(request, f"Успешно отправлено {success_count} сообщений")
    
    if error_count > 0:
        messages.warning(request, f"Не удалось отправить {error_count} сообщений. Проверьте журнал для деталей.")
    
    return redirect('crm:bulk_message_form')

@marketer_required
def preview_recipients(request):
    """AJAX-представление для предварительного просмотра получателей сообщений"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    
    # Получаем параметры из запроса
    source_filter = request.GET.get('source_filter')
    stage_filter = request.GET.get('stage_filter')
    status_filter = request.GET.get('status_filter')
    
    # Базовый запрос для лидов
    leads_query = Lead.objects.filter(phone_number__isnull=False)
    
    # Применяем фильтры
    if source_filter:
        leads_query = leads_query.filter(source__name=source_filter)
    
    if stage_filter:
        leads_query = leads_query.filter(current_stage__name=stage_filter)
    
    if status_filter:
        leads_query = leads_query.filter(status=status_filter)
    
    # Получаем лидов
    leads = leads_query.all()
    
    # Формируем данные для ответа
    recipients = []
    for lead in leads[:20]:  # Ограничиваем до 20 для предварительного просмотра
        recipients.append({
            'id': lead.id,
            'name': lead.full_name,
            'phone': lead.phone_number,
            'source': lead.source.name if lead.source else 'Не указан',
            'stage': lead.current_stage.name if lead.current_stage else 'Не указан',
        })
    
    total_count = leads_query.count()
    
    return JsonResponse({
        'recipients': recipients,
        'total_count': total_count,
        'preview_count': len(recipients),
    })

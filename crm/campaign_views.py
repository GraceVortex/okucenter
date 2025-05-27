import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from .models import Campaign, CampaignChannel, Lead, LeadSource
from .views import marketer_required

logger = logging.getLogger(__name__)

def campaign_list(request):
    """Отображение списка маркетинговых кампаний"""
    # Проверка аутентификации пользователя
    if not request.user.is_authenticated:
        messages.error(request, 'Вы должны войти в систему для доступа к этой странице.')
        return redirect('accounts:login')
    
    # Проверка прав доступа - используем безопасные проверки атрибутов
    is_marketer = False
    is_admin = False
    
    try:
        if hasattr(request.user, 'is_marketer'):
            is_marketer = request.user.is_marketer
        if hasattr(request.user, 'is_admin'):
            is_admin = request.user.is_admin
    except Exception as e:
        logger.error(f"Ошибка при проверке прав пользователя: {str(e)}")
    
    if not (is_marketer or is_admin):
        messages.error(request, 'У вас нет прав для доступа к этой странице. Требуется роль маркетолога или администратора.')
        return redirect('core:home')
    
    # Фильтры
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('q', '')
    
    try:
        # Базовый запрос для кампаний
        campaigns_query = Campaign.objects.all()
        
        # Если это маркетолог (не админ), показываем только его кампании
        if is_marketer and not is_admin:
            campaigns_query = campaigns_query.filter(manager=request.user)
        
        # Применяем фильтры
        if status_filter:
            campaigns_query = campaigns_query.filter(status=status_filter)
        
        if search_query:
            campaigns_query = campaigns_query.filter(
                Q(name__icontains=search_query) | 
                Q(description__icontains=search_query)
            )
        
        # Получаем кампании без аннотаций, которые могут вызвать ошибки
        campaigns = campaigns_query.order_by('-start_date')
        
        # Добавляем информацию о количестве лидов для каждой кампании
        # Временно устанавливаем фиктивное значение, так как связь между Campaign и Lead не определена
        for campaign in campaigns:
            campaign.leads_count = 0
    
    except Exception as e:
        logger.error(f"Ошибка при получении кампаний: {str(e)}")
        campaigns = []
    
    context = {
        'campaigns': campaigns,
        'status_filter': status_filter,
        'search_query': search_query,
        'status_choices': Campaign.CAMPAIGN_STATUS_CHOICES,
    }
    
    return render(request, 'crm/campaign_list.html', context)

@marketer_required
def campaign_detail(request, campaign_id):
    """Детальная информация о кампании"""
    campaign = get_object_or_404(Campaign, id=campaign_id)
    
    # Если это маркетолог (не админ), проверяем доступ
    if request.user.is_marketer and not request.user.is_admin and campaign.manager != request.user:
        messages.error(request, "У вас нет доступа к этой кампании")
        return redirect('crm:campaign_list')
    
    # Получаем лидов, связанных с кампанией
    # Временное решение: получаем всех лидов, так как связь между Lead и Campaign не определена
    leads = Lead.objects.all()
    
    # Статистика по каналам
    channels = CampaignChannel.objects.filter(campaign=campaign)
    # Временно убираем подсчет лидов, так как связь между CampaignChannel и Lead не определена
    
    # Статистика по источникам лидов
    try:
        sources = LeadSource.objects.all().annotate(
            leads_count=Count('leads')
        ).order_by('-leads_count')
    except Exception as e:
        logger.error(f"Ошибка при получении источников: {str(e)}")
        sources = LeadSource.objects.all()
    
    # Добавляем дополнительные проверки для избежания ошибок
    try:
        leads_count = leads.count()
        converted_count = leads.filter(status='converted').count()
    except Exception as e:
        logger.error(f"Ошибка при подсчете лидов: {str(e)}")
        leads_count = 0
        converted_count = 0
    
    context = {
        'campaign': campaign,
        'leads': leads,
        'channels': channels,
        'sources': sources,
        'leads_count': leads_count,
        'converted_count': converted_count,
    }
    
    return render(request, 'crm/campaign_detail.html', context)

@marketer_required
def campaign_create(request):
    """Создание новой кампании"""
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        budget = request.POST.get('budget')
        target_audience = request.POST.get('target_audience')
        
        if not name or not start_date:
            messages.error(request, "Название и дата начала обязательны для заполнения")
            return redirect('crm:campaign_create')
        
        campaign = Campaign.objects.create(
            name=name,
            description=description,
            start_date=start_date,
            end_date=end_date if end_date else None,
            budget=budget if budget else 0,
            target_audience=target_audience,
            manager=request.user,
            status='active' if timezone.now().date() >= timezone.datetime.strptime(start_date, '%Y-%m-%d').date() else 'planned'
        )
        
        # Создаем каналы кампании
        channels = request.POST.getlist('channels')
        for channel in channels:
            CampaignChannel.objects.create(
                campaign=campaign,
                channel_type=channel,
                name=f"{campaign.name} - {dict(CampaignChannel.CHANNEL_TYPE_CHOICES).get(channel, channel)}"
            )
        
        messages.success(request, f"Кампания '{campaign.name}' успешно создана")
        return redirect('crm:campaign_detail', campaign_id=campaign.id)
    
    context = {
        'channel_types': CampaignChannel.CHANNEL_TYPE_CHOICES,
    }
    
    return render(request, 'crm/campaign_form.html', context)

@marketer_required
def campaign_update(request, campaign_id):
    """Обновление существующей кампании"""
    campaign = get_object_or_404(Campaign, id=campaign_id)
    
    # Если это маркетолог (не админ), проверяем доступ
    if request.user.is_marketer and not request.user.is_admin and campaign.manager != request.user:
        messages.error(request, "У вас нет доступа к редактированию этой кампании")
        return redirect('crm:campaign_list')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        budget = request.POST.get('budget')
        target_audience = request.POST.get('target_audience')
        status = request.POST.get('status')
        
        if not name or not start_date:
            messages.error(request, "Название и дата начала обязательны для заполнения")
            return redirect('crm:campaign_update', campaign_id=campaign.id)
        
        campaign.name = name
        campaign.description = description
        campaign.start_date = start_date
        campaign.end_date = end_date if end_date else None
        campaign.budget = budget if budget else 0
        campaign.target_audience = target_audience
        campaign.status = status
        campaign.save()
        
        # Обновляем каналы кампании
        # Сначала удаляем существующие
        campaign.channels.all().delete()
        
        # Затем создаем новые
        channels = request.POST.getlist('channels')
        for channel in channels:
            CampaignChannel.objects.create(
                campaign=campaign,
                channel_type=channel,
                name=f"{campaign.name} - {dict(CampaignChannel.CHANNEL_TYPE_CHOICES).get(channel, channel)}"
            )
        
        messages.success(request, f"Кампания '{campaign.name}' успешно обновлена")
        return redirect('crm:campaign_detail', campaign_id=campaign.id)
    
    context = {
        'campaign': campaign,
        'channel_types': CampaignChannel.CHANNEL_TYPE_CHOICES,
        'selected_channels': [channel.channel_type for channel in campaign.channels.all()],
    }
    
    return render(request, 'crm/campaign_form.html', context)

@marketer_required
def campaign_leads(request, campaign_id):
    """Отображение лидов, связанных с кампанией"""
    campaign = get_object_or_404(Campaign, id=campaign_id)
    
    # Если это маркетолог (не админ), проверяем доступ
    if request.user.is_marketer and not request.user.is_admin and campaign.manager != request.user:
        messages.error(request, "У вас нет доступа к этой кампании")
        return redirect('crm:campaign_list')
    
    # Фильтры
    status_filter = request.GET.get('status', '')
    source_filter = request.GET.get('source', '')
    search_query = request.GET.get('q', '')
    
    # Базовый запрос для лидов
    # Временное решение: получаем всех лидов, так как связь между Lead и Campaign не определена
    leads_query = Lead.objects.all()
    
    # Применяем фильтры
    if status_filter:
        leads_query = leads_query.filter(status=status_filter)
    
    if source_filter:
        leads_query = leads_query.filter(source_id=source_filter)
    
    if search_query:
        leads_query = leads_query.filter(
            Q(full_name__icontains=search_query) | 
            Q(phone_number__icontains=search_query) | 
            Q(email__icontains=search_query)
        )
    
    # Получаем источники для фильтрации
    # Временное решение: получаем все источники
    sources = LeadSource.objects.all().distinct()
    
    context = {
        'campaign': campaign,
        'leads': leads_query,
        'sources': sources,
        'status_filter': status_filter,
        'source_filter': source_filter,
        'search_query': search_query,
        'status_choices': Lead.STATUS_CHOICES,
    }
    
    return render(request, 'crm/campaign_leads.html', context)

import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from accounts.models import User
from .models import Lead, LeadSource, SaleStage
from .views import marketer_required

logger = logging.getLogger(__name__)

@marketer_required
def sales_funnel(request):
    """Отображение воронки продаж с возможностью перетаскивания лидов между этапами"""
    # Получаем все активные этапы воронки
    stages = SaleStage.objects.filter(is_active=True).order_by('order')
    
    # Фильтры
    source_filter = request.GET.get('source', '')
    assigned_to_filter = request.GET.get('assigned_to', '')
    search_query = request.GET.get('q', '')
    
    # Базовый запрос для лидов
    leads_query = Lead.objects.filter(status__in=['new', 'in_progress', 'qualified'])
    
    # Если это маркетолог (не админ), показываем только его лидов
    if request.user.is_marketer and not request.user.is_admin:
        leads_query = leads_query.filter(assigned_to=request.user)
    
    # Применяем фильтры
    if source_filter:
        leads_query = leads_query.filter(source_id=source_filter)
    
    if assigned_to_filter:
        leads_query = leads_query.filter(assigned_to_id=assigned_to_filter)
    
    if search_query:
        leads_query = leads_query.filter(
            Q(full_name__icontains=search_query) | 
            Q(phone_number__icontains=search_query) | 
            Q(email__icontains=search_query)
        )
    
    # Группируем лидов по этапам
    funnel_data = []
    for stage in stages:
        stage_leads = leads_query.filter(current_stage=stage)
        funnel_data.append({
            'stage': stage,
            'leads': stage_leads,
            'count': stage_leads.count(),
        })
    
    # Данные для фильтров
    lead_sources = LeadSource.objects.filter(is_active=True)
    marketers = User.objects.filter(user_type='marketer', is_active=True)
    
    context = {
        'funnel_data': funnel_data,
        'lead_sources': lead_sources,
        'marketers': marketers,
        'source_filter': source_filter,
        'assigned_to_filter': assigned_to_filter,
        'search_query': search_query,
    }
    
    return render(request, 'crm/sales_funnel.html', context)

@marketer_required
def funnel_statistics(request):
    """Статистика по воронке продаж"""
    # Получаем все активные этапы воронки
    stages = SaleStage.objects.filter(is_active=True).order_by('order')
    
    # Статистика по этапам
    stage_stats = []
    total_leads = 0
    
    for stage in stages:
        stage_leads_count = Lead.objects.filter(current_stage=stage).count()
        total_leads += stage_leads_count
        
        stage_stats.append({
            'stage': stage,
            'count': stage_leads_count,
            'percentage': 0,  # Заполним позже
        })
    
    # Рассчитываем процентное соотношение
    if total_leads > 0:
        for stat in stage_stats:
            stat['percentage'] = round((stat['count'] / total_leads) * 100, 1)
    
    # Статистика по конверсии между этапами
    conversion_stats = []
    for i in range(len(stages) - 1):
        current_stage = stages[i]
        next_stage = stages[i + 1]
        
        current_count = stage_stats[i]['count']
        next_count = stage_stats[i + 1]['count']
        
        conversion_rate = 0
        if current_count > 0:
            conversion_rate = round((next_count / current_count) * 100, 1)
        
        conversion_stats.append({
            'from_stage': current_stage,
            'to_stage': next_stage,
            'conversion_rate': conversion_rate,
            'goal': current_stage.conversion_goal or 0,
        })
    
    # Статистика по источникам лидов
    source_stats = []
    lead_sources = LeadSource.objects.filter(is_active=True)
    
    for source in lead_sources:
        source_leads = Lead.objects.filter(source=source)
        converted_leads = source_leads.filter(status='converted')
        
        conversion_rate = 0
        if source_leads.count() > 0:
            conversion_rate = round((converted_leads.count() / source_leads.count()) * 100, 1)
        
        source_stats.append({
            'source': source,
            'total': source_leads.count(),
            'converted': converted_leads.count(),
            'conversion_rate': conversion_rate,
        })
    
    context = {
        'stage_stats': stage_stats,
        'conversion_stats': conversion_stats,
        'source_stats': source_stats,
        'total_leads': total_leads,
    }
    
    return render(request, 'crm/funnel_statistics.html', context)

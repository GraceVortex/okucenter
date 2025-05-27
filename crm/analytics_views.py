import logging
from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Sum, F, FloatField
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from .models import Campaign, Lead, LeadSource, SaleStage, Interaction
from .views import marketer_required

logger = logging.getLogger(__name__)

@marketer_required
def campaign_analytics(request):
    """Аналитика по маркетинговым кампаниям с возможностью сравнения периодов"""
    # Получаем период из запроса или используем текущий месяц по умолчанию
    period = request.GET.get('period', 'current_month')
    comparison = request.GET.get('comparison', 'previous_period')
    
    # Определяем даты на основе выбранного периода
    today = timezone.now().date()
    
    if period == 'current_month':
        start_date = today.replace(day=1)
        next_month = today.month + 1 if today.month < 12 else 1
        next_month_year = today.year if today.month < 12 else today.year + 1
        end_date = today.replace(year=next_month_year, month=next_month, day=1) - timedelta(days=1)
        period_name = f"Текущий месяц ({start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')})"
    elif period == 'last_month':
        # Первый день предыдущего месяца
        last_month = today.month - 1 if today.month > 1 else 12
        last_month_year = today.year if today.month > 1 else today.year - 1
        start_date = today.replace(year=last_month_year, month=last_month, day=1)
        # Последний день предыдущего месяца
        end_date = today.replace(day=1) - timedelta(days=1)
        period_name = f"Прошлый месяц ({start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')})"
    elif period == 'last_30_days':
        start_date = today - timedelta(days=30)
        end_date = today
        period_name = f"Последние 30 дней ({start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')})"
    elif period == 'last_90_days':
        start_date = today - timedelta(days=90)
        end_date = today
        period_name = f"Последние 90 дней ({start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')})"
    elif period == 'year_to_date':
        start_date = today.replace(month=1, day=1)
        end_date = today
        period_name = f"С начала года ({start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')})"
    else:  # По умолчанию - текущий месяц
        start_date = today.replace(day=1)
        next_month = today.month + 1 if today.month < 12 else 1
        next_month_year = today.year if today.month < 12 else today.year + 1
        end_date = today.replace(year=next_month_year, month=next_month, day=1) - timedelta(days=1)
        period_name = f"Текущий месяц ({start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')})"
    
    # Определяем даты для сравнения
    if comparison == 'previous_period':
        # Предыдущий период такой же длительности
        period_length = (end_date - start_date).days + 1
        compare_end_date = start_date - timedelta(days=1)
        compare_start_date = compare_end_date - timedelta(days=period_length-1)
        comparison_name = f"Предыдущий период ({compare_start_date.strftime('%d.%m.%Y')} - {compare_end_date.strftime('%d.%m.%Y')})"
    elif comparison == 'same_period_last_year':
        # Тот же период в прошлом году
        compare_start_date = start_date.replace(year=start_date.year-1)
        compare_end_date = end_date.replace(year=end_date.year-1)
        comparison_name = f"Тот же период год назад ({compare_start_date.strftime('%d.%m.%Y')} - {compare_end_date.strftime('%d.%m.%Y')})"
    else:  # По умолчанию - предыдущий период
        period_length = (end_date - start_date).days + 1
        compare_end_date = start_date - timedelta(days=1)
        compare_start_date = compare_end_date - timedelta(days=period_length-1)
        comparison_name = f"Предыдущий период ({compare_start_date.strftime('%d.%m.%Y')} - {compare_end_date.strftime('%d.%m.%Y')})"
    
    # Получаем все активные и завершенные кампании
    campaigns = Campaign.objects.filter(status__in=['active', 'completed'])
    
    # Статистика по кампаниям для текущего периода
    campaign_stats = []
    for campaign in campaigns:
        # Лиды за текущий период
        current_leads = Lead.objects.filter(
            campaign=campaign,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        current_leads_count = current_leads.count()
        current_converted_count = current_leads.filter(status='converted').count()
        
        # Лиды за период для сравнения
        compare_leads = Lead.objects.filter(
            campaign=campaign,
            created_at__date__gte=compare_start_date,
            created_at__date__lte=compare_end_date
        )
        compare_leads_count = compare_leads.count()
        compare_converted_count = compare_leads.filter(status='converted').count()
        
        # Расчет конверсии для текущего периода
        current_conversion_rate = 0
        if current_leads_count > 0:
            current_conversion_rate = round((current_converted_count / current_leads_count) * 100, 1)
        
        # Расчет конверсии для периода сравнения
        compare_conversion_rate = 0
        if compare_leads_count > 0:
            compare_conversion_rate = round((compare_converted_count / compare_leads_count) * 100, 1)
        
        # Расчет изменения показателей
        leads_change = current_leads_count - compare_leads_count
        leads_change_percent = 0
        if compare_leads_count > 0:
            leads_change_percent = round((leads_change / compare_leads_count) * 100, 1)
        
        conversion_change = current_conversion_rate - compare_conversion_rate
        
        # Расчет ROI для текущего периода
        # Предполагаем, что у каждого конвертированного лида есть средняя стоимость
        avg_lead_value = 50000  # Средняя стоимость конвертированного лида (в тенге)
        
        # Пропорциональный бюджет кампании за период
        total_days = (campaign.end_date - campaign.start_date).days
        if total_days <= 0:  # Защита от деления на ноль
            total_days = 1
        
        period_days = (end_date - start_date).days + 1
        period_budget = (campaign.budget / total_days) * period_days
        
        current_total_revenue = current_converted_count * avg_lead_value
        current_roi = 0
        if period_budget > 0:
            current_roi = round(((current_total_revenue - period_budget) / period_budget) * 100, 1)
        
        # ROI для периода сравнения
        compare_period_days = (compare_end_date - compare_start_date).days + 1
        compare_period_budget = (campaign.budget / total_days) * compare_period_days
        
        compare_total_revenue = compare_converted_count * avg_lead_value
        compare_roi = 0
        if compare_period_budget > 0:
            compare_roi = round(((compare_total_revenue - compare_period_budget) / compare_period_budget) * 100, 1)
        
        roi_change = current_roi - compare_roi
        
        campaign_stats.append({
            'campaign': campaign,
            'current_leads_count': current_leads_count,
            'current_converted_count': current_converted_count,
            'current_conversion_rate': current_conversion_rate,
            'current_total_revenue': current_total_revenue,
            'current_roi': current_roi,
            'compare_leads_count': compare_leads_count,
            'compare_converted_count': compare_converted_count,
            'compare_conversion_rate': compare_conversion_rate,
            'compare_total_revenue': compare_total_revenue,
            'compare_roi': compare_roi,
            'leads_change': leads_change,
            'leads_change_percent': leads_change_percent,
            'conversion_change': conversion_change,
            'roi_change': roi_change
        })
    
    # Сортируем по ROI текущего периода (от большего к меньшему)
    campaign_stats.sort(key=lambda x: x['current_roi'], reverse=True)
    
    # Статистика по источникам лидов для текущего периода
    sources = LeadSource.objects.filter(is_active=True)
    source_stats = []
    
    for source in sources:
        # Лиды из источника за текущий период
        current_source_leads = Lead.objects.filter(
            source=source,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        current_source_leads_count = current_source_leads.count()
        current_source_converted_count = current_source_leads.filter(status='converted').count()
        
        # Лиды из источника за период для сравнения
        compare_source_leads = Lead.objects.filter(
            source=source,
            created_at__date__gte=compare_start_date,
            created_at__date__lte=compare_end_date
        )
        compare_source_leads_count = compare_source_leads.count()
        compare_source_converted_count = compare_source_leads.filter(status='converted').count()
        
        # Расчет конверсии для текущего периода
        current_source_conversion_rate = 0
        if current_source_leads_count > 0:
            current_source_conversion_rate = round((current_source_converted_count / current_source_leads_count) * 100, 1)
        
        # Расчет конверсии для периода сравнения
        compare_source_conversion_rate = 0
        if compare_source_leads_count > 0:
            compare_source_conversion_rate = round((compare_source_converted_count / compare_source_leads_count) * 100, 1)
        
        # Расчет изменения показателей
        source_leads_change = current_source_leads_count - compare_source_leads_count
        source_leads_change_percent = 0
        if compare_source_leads_count > 0:
            source_leads_change_percent = round((source_leads_change / compare_source_leads_count) * 100, 1)
        
        source_conversion_change = current_source_conversion_rate - compare_source_conversion_rate
        
        source_stats.append({
            'source': source,
            'current_leads_count': current_source_leads_count,
            'current_converted_count': current_source_converted_count,
            'current_conversion_rate': current_source_conversion_rate,
            'compare_leads_count': compare_source_leads_count,
            'compare_converted_count': compare_source_converted_count,
            'compare_conversion_rate': compare_source_conversion_rate,
            'leads_change': source_leads_change,
            'leads_change_percent': source_leads_change_percent,
            'conversion_change': source_conversion_change
        })
    
    # Сортируем по конверсии текущего периода (от большей к меньшей)
    source_stats.sort(key=lambda x: x['current_conversion_rate'], reverse=True)
    
    # Данные для графика динамики лидов за текущий период
    leads_by_date = Lead.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    ).annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    # Данные для графика динамики лидов за период сравнения
    compare_leads_by_date = Lead.objects.filter(
        created_at__date__gte=compare_start_date,
        created_at__date__lte=compare_end_date
    ).annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    # Преобразуем в формат для графика
    dates = []
    lead_counts = []
    compare_dates = []
    compare_lead_counts = []
    
    for item in leads_by_date:
        dates.append(item['date'].strftime('%d.%m.%Y'))
        lead_counts.append(item['count'])
    
    for item in compare_leads_by_date:
        compare_dates.append(item['date'].strftime('%d.%m.%Y'))
        compare_lead_counts.append(item['count'])
    
    # Общая статистика за период
    total_current_leads = Lead.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    ).count()
    
    total_compare_leads = Lead.objects.filter(
        created_at__date__gte=compare_start_date,
        created_at__date__lte=compare_end_date
    ).count()
    
    total_leads_change = total_current_leads - total_compare_leads
    total_leads_change_percent = 0
    if total_compare_leads > 0:
        total_leads_change_percent = round((total_leads_change / total_compare_leads) * 100, 1)
    
    context = {
        'campaign_stats': campaign_stats,
        'source_stats': source_stats,
        'dates': dates,
        'lead_counts': lead_counts,
        'compare_dates': compare_dates,
        'compare_lead_counts': compare_lead_counts,
        'period': period,
        'comparison': comparison,
        'period_name': period_name,
        'comparison_name': comparison_name,
        'start_date': start_date,
        'end_date': end_date,
        'compare_start_date': compare_start_date,
        'compare_end_date': compare_end_date,
        'total_current_leads': total_current_leads,
        'total_compare_leads': total_compare_leads,
        'total_leads_change': total_leads_change,
        'total_leads_change_percent': total_leads_change_percent
    }

    return render(request, 'crm/campaign_analytics.html', context)

@marketer_required
def lead_acquisition_cost(request):
    """Стоимость привлечения лидов по кампаниям и источникам с возможностью сравнения периодов"""
    # Получаем период из запроса или используем текущий месяц по умолчанию
    period = request.GET.get('period', 'current_month')
    comparison = request.GET.get('comparison', 'previous_period')
    
    # Определяем даты на основе выбранного периода
    today = timezone.now().date()
    
    if period == 'current_month':
        start_date = today.replace(day=1)
        next_month = today.month + 1 if today.month < 12 else 1
        next_month_year = today.year if today.month < 12 else today.year + 1
        end_date = today.replace(year=next_month_year, month=next_month, day=1) - timedelta(days=1)
        period_name = f"Текущий месяц ({start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')})"
    elif period == 'last_month':
        # Первый день предыдущего месяца
        last_month = today.month - 1 if today.month > 1 else 12
        last_month_year = today.year if today.month > 1 else today.year - 1
        start_date = today.replace(year=last_month_year, month=last_month, day=1)
        # Последний день предыдущего месяца
        end_date = today.replace(day=1) - timedelta(days=1)
        period_name = f"Прошлый месяц ({start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')})"
    elif period == 'last_30_days':
        start_date = today - timedelta(days=30)
        end_date = today
        period_name = f"Последние 30 дней ({start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')})"
    elif period == 'last_90_days':
        start_date = today - timedelta(days=90)
        end_date = today
        period_name = f"Последние 90 дней ({start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')})"
    elif period == 'year_to_date':
        start_date = today.replace(month=1, day=1)
        end_date = today
        period_name = f"С начала года ({start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')})"
    else:  # По умолчанию - текущий месяц
        start_date = today.replace(day=1)
        next_month = today.month + 1 if today.month < 12 else 1
        next_month_year = today.year if today.month < 12 else today.year + 1
        end_date = today.replace(year=next_month_year, month=next_month, day=1) - timedelta(days=1)
        period_name = f"Текущий месяц ({start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')})"
    
    # Определяем даты для сравнения
    if comparison == 'previous_period':
        # Предыдущий период такой же длительности
        period_length = (end_date - start_date).days + 1
        compare_end_date = start_date - timedelta(days=1)
        compare_start_date = compare_end_date - timedelta(days=period_length-1)
        comparison_name = f"Предыдущий период ({compare_start_date.strftime('%d.%m.%Y')} - {compare_end_date.strftime('%d.%m.%Y')})"
    elif comparison == 'same_period_last_year':
        # Тот же период в прошлом году
        compare_start_date = start_date.replace(year=start_date.year-1)
        compare_end_date = end_date.replace(year=end_date.year-1)
        comparison_name = f"Тот же период год назад ({compare_start_date.strftime('%d.%m.%Y')} - {compare_end_date.strftime('%d.%m.%Y')})"
    else:  # По умолчанию - предыдущий период
        period_length = (end_date - start_date).days + 1
        compare_end_date = start_date - timedelta(days=1)
        compare_start_date = compare_end_date - timedelta(days=period_length-1)
        comparison_name = f"Предыдущий период ({compare_start_date.strftime('%d.%m.%Y')} - {compare_end_date.strftime('%d.%m.%Y')})"
    
    # Статистика по стоимости привлечения лидов из разных кампаний
    campaign_lac_stats = []
    campaigns = Campaign.objects.filter(status__in=['active', 'completed'])
    
    for campaign in campaigns:
        # Количество лидов из этой кампании за текущий период
        current_leads = Lead.objects.filter(
            campaign=campaign,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        current_leads_count = current_leads.count()
        
        # Количество лидов из этой кампании за период сравнения
        compare_leads = Lead.objects.filter(
            campaign=campaign,
            created_at__date__gte=compare_start_date,
            created_at__date__lte=compare_end_date
        )
        compare_leads_count = compare_leads.count()
        
        # Пропорциональный бюджет кампании за текущий период
        total_days = (campaign.end_date - campaign.start_date).days
        if total_days <= 0:  # Защита от деления на ноль
            total_days = 1
        
        period_days = (end_date - start_date).days + 1
        current_budget = (campaign.budget / total_days) * period_days
        
        # Пропорциональный бюджет кампании за период сравнения
        compare_period_days = (compare_end_date - compare_start_date).days + 1
        compare_budget = (campaign.budget / total_days) * compare_period_days
        
        # Стоимость привлечения лида за текущий период
        current_lac = 0
        if current_leads_count > 0 and current_budget > 0:
            current_lac = round(current_budget / current_leads_count, 2)
        
        # Стоимость привлечения лида за период сравнения
        compare_lac = 0
        if compare_leads_count > 0 and compare_budget > 0:
            compare_lac = round(compare_budget / compare_leads_count, 2)
        
        # Изменение стоимости привлечения
        lac_change = current_lac - compare_lac
        lac_change_percent = 0
        if compare_lac > 0:
            lac_change_percent = round((lac_change / compare_lac) * 100, 1)
        
        campaign_lac_stats.append({
            'campaign': campaign,
            'current_leads_count': current_leads_count,
            'current_budget': current_budget,
            'current_lac': current_lac,
            'compare_leads_count': compare_leads_count,
            'compare_budget': compare_budget,
            'compare_lac': compare_lac,
            'lac_change': lac_change,
            'lac_change_percent': lac_change_percent
        })
    
    # Сортируем по текущему LAC (от меньшего к большему)
    campaign_lac_stats.sort(key=lambda x: x['current_lac'] if x['current_lac'] > 0 else float('inf'))
    
    # Статистика по стоимости привлечения лидов из разных источников
    source_lac_stats = []
    sources = LeadSource.objects.filter(is_active=True)
    
    for source in sources:
        # Получаем лидов из этого источника за текущий период
        current_source_leads = Lead.objects.filter(
            source=source,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        current_source_leads_count = current_source_leads.count()
        
        # Получаем лидов из этого источника за период сравнения
        compare_source_leads = Lead.objects.filter(
            source=source,
            created_at__date__gte=compare_start_date,
            created_at__date__lte=compare_end_date
        )
        compare_source_leads_count = compare_source_leads.count()
        
        # Получаем все кампании, использующие этот источник
        source_campaigns = Campaign.objects.filter(
            channels__leads__source=source
        ).distinct()
        
        # Рассчитываем пропорциональный бюджет для текущего периода
        current_total_budget = 0
        for campaign in source_campaigns:
            total_days = (campaign.end_date - campaign.start_date).days
            if total_days <= 0:
                total_days = 1
            
            period_days = (end_date - start_date).days + 1
            current_total_budget += (campaign.budget / total_days) * period_days
        
        # Рассчитываем пропорциональный бюджет для периода сравнения
        compare_total_budget = 0
        for campaign in source_campaigns:
            total_days = (campaign.end_date - campaign.start_date).days
            if total_days <= 0:
                total_days = 1
            
            compare_period_days = (compare_end_date - compare_start_date).days + 1
            compare_total_budget += (campaign.budget / total_days) * compare_period_days
        
        # Стоимость привлечения лида из этого источника за текущий период
        current_source_lac = 0
        if current_source_leads_count > 0 and current_total_budget > 0:
            current_source_lac = round(current_total_budget / current_source_leads_count, 2)
        
        # Стоимость привлечения лида из этого источника за период сравнения
        compare_source_lac = 0
        if compare_source_leads_count > 0 and compare_total_budget > 0:
            compare_source_lac = round(compare_total_budget / compare_source_leads_count, 2)
        
        # Изменение стоимости привлечения
        source_lac_change = current_source_lac - compare_source_lac
        source_lac_change_percent = 0
        if compare_source_lac > 0:
            source_lac_change_percent = round((source_lac_change / compare_source_lac) * 100, 1)
        
        source_lac_stats.append({
            'source': source,
            'current_leads_count': current_source_leads_count,
            'current_total_budget': current_total_budget,
            'current_lac': current_source_lac,
            'compare_leads_count': compare_source_leads_count,
            'compare_total_budget': compare_total_budget,
            'compare_lac': compare_source_lac,
            'lac_change': source_lac_change,
            'lac_change_percent': source_lac_change_percent
        })
    
    # Сортируем по текущему LAC (от меньшего к большему)
    source_lac_stats.sort(key=lambda x: x['current_lac'] if x['current_lac'] > 0 else float('inf'))
    
    context = {
        'campaign_lac_stats': campaign_lac_stats,
        'source_lac_stats': source_lac_stats,
        'period': period,
        'comparison': comparison,
        'period_name': period_name,
        'comparison_name': comparison_name,
        'start_date': start_date,
        'end_date': end_date,
        'compare_start_date': compare_start_date,
        'compare_end_date': compare_end_date
    }
    
    return render(request, 'crm/lead_acquisition_cost.html', context)

@marketer_required
def interaction_analytics(request):
    """Аналитика по взаимодействиям с лидами"""
    # Статистика по типам взаимодействий
    interaction_types = Interaction.objects.values('interaction_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Статистика по результатам взаимодействий
    interaction_results = Interaction.objects.values('result').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Статистика по взаимодействиям за последние 30 дней
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    interactions_by_date = Interaction.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    ).annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    # Преобразуем в формат для графика
    dates = []
    interaction_counts = []
    
    for item in interactions_by_date:
        dates.append(item['date'].strftime('%d.%m.%Y'))
        interaction_counts.append(item['count'])
    
    # Статистика по маркетологам
    marketer_stats = Interaction.objects.values(
        'created_by__id', 'created_by__first_name', 'created_by__last_name'
    ).annotate(
        count=Count('id'),
        positive_count=Count('id', filter=F('result')=='positive'),
        negative_count=Count('id', filter=F('result')=='negative'),
        neutral_count=Count('id', filter=F('result')=='neutral')
    ).order_by('-count')
    
    # Добавляем процент положительных результатов
    for stat in marketer_stats:
        if stat['count'] > 0:
            stat['positive_percentage'] = round((stat['positive_count'] / stat['count']) * 100, 1)
        else:
            stat['positive_percentage'] = 0
    
    context = {
        'interaction_types': interaction_types,
        'interaction_results': interaction_results,
        'dates': dates,
        'interaction_counts': interaction_counts,
        'marketer_stats': marketer_stats
    }
    
    return render(request, 'crm/interaction_analytics.html', context)

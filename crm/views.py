import logging
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q, F, ExpressionWrapper, fields
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from django.core.paginator import Paginator
from django.urls import reverse
from accounts.models import User, Student, Marketer
from .models import Lead, LeadSource, SaleStage, LeadStatusHistory, Interaction, Campaign, CampaignChannel
from .models import MetaBusinessAccount, SocialMessage
# Импортируем модели новой CRM-системы
from .models_new import Contact, Company, Deal, Pipeline, Stage
from .models_activities import Activity, Task
from .models_integrations import Conversation, Message, Integration

logger = logging.getLogger(__name__)

# Декоратор для проверки прав маркетолога
def marketer_required(view_func):
    """Декоратор, который проверяет, является ли пользователь маркетологом или администратором"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Вы должны войти в систему для доступа к этой странице.')
            return redirect('login')
        
        if not (request.user.is_marketer or request.user.is_admin):
            messages.error(request, 'У вас нет прав для доступа к этой странице.')
            return redirect('home')
            
        return view_func(request, *args, **kwargs)
    return wrapper

# Представления для дашборда CRM
def crm_dashboard(request):
    """Главный дашборд CRM с ключевыми метриками и последними активностями"""
    # Проверка аутентификации пользователя
    if not request.user.is_authenticated:
        messages.error(request, 'Вы должны войти в систему для доступа к этой странице.')
        return redirect('accounts:login')
    
    # Проверка прав доступа
    if not (request.user.is_marketer or request.user.is_admin):
        messages.error(request, 'У вас нет прав для доступа к этой странице. Требуется роль маркетолога или администратора.')
        return redirect('core:home')
    
    today = timezone.now().date()
    last_week = today - timezone.timedelta(days=7)
    last_month = today - timezone.timedelta(days=30)
    
    try:
        # Статистика по лидам (из старой системы для сравнения)
        new_leads_count = Lead.objects.filter(created_at__gte=last_week).count()
        new_leads_prev = Lead.objects.filter(
            created_at__gte=last_week - timezone.timedelta(days=7),
            created_at__lt=last_week
        ).count()
        
        # Вычисляем процентное изменение
        if new_leads_prev > 0:
            new_leads_diff = ((new_leads_count - new_leads_prev) / new_leads_prev) * 100
        else:
            new_leads_diff = 0
        
        # Статистика по сделкам
        active_deals_count = Deal.objects.filter(status='open').count()
        active_deals_amount = Deal.objects.filter(status='open').aggregate(total=Sum('amount'))['total'] or 0
        active_deals_prev = Deal.objects.filter(
            status='open',
            created_at__lt=last_month
        ).count()
        
        if active_deals_prev > 0:
            active_deals_diff = ((active_deals_count - active_deals_prev) / active_deals_prev) * 100
        else:
            active_deals_diff = 0
        
        # Выигранные сделки
        won_deals_count = Deal.objects.filter(status='won').count()
        won_deals_amount = Deal.objects.filter(status='won').aggregate(total=Sum('amount'))['total'] or 0
        won_deals_prev = Deal.objects.filter(
            status='won',
            created_at__lt=last_month
        ).count()
        
        if won_deals_prev > 0:
            won_deals_diff = ((won_deals_count - won_deals_prev) / won_deals_prev) * 100
        else:
            won_deals_diff = 0
        
        # Конверсия
        total_leads = Lead.objects.count()
        if total_leads > 0:
            conversion_rate = (Deal.objects.count() / total_leads) * 100
        else:
            conversion_rate = 0
        
        # Данные для воронки продаж
        pipelines = Pipeline.objects.all()
        stages = Stage.objects.all().order_by('order')
        
        funnel_stages = []
        funnel_counts = []
        funnel_amounts = []
        
        for stage in stages:
            funnel_stages.append(stage.name)
            stage_deals = Deal.objects.filter(stage=stage)
            funnel_counts.append(stage_deals.count())
            stage_amount = stage_deals.aggregate(total=Sum('amount'))['total'] or 0
            funnel_amounts.append(stage_amount)
        
        # Источники лидов
        lead_sources = []
        lead_sources_counts = []
        lead_sources_percentages = []
        
        sources = LeadSource.objects.all()
        for source in sources:
            lead_sources.append(source.name)
            source_count = Lead.objects.filter(source=source).count()
            lead_sources_counts.append(source_count)
            if total_leads > 0:
                percentage = (source_count / total_leads) * 100
            else:
                percentage = 0
            lead_sources_percentages.append(round(percentage, 1))
        
        # Последние активности
        recent_activities = Activity.objects.select_related('assigned_to').order_by('-created_at')[:5]
        
        # Последние сообщения
        recent_messages = Message.objects.select_related('contact', 'conversation').order_by('-sent_at')[:5]
        
        # Предстоящие задачи
        upcoming_tasks = Task.objects.filter(
            due_date__gte=today,
            status__in=['not_started', 'in_progress']
        ).order_by('due_date')[:5]
        
        # Последние сделки
        recent_deals = Deal.objects.select_related('contact').order_by('-created_at')[:5]
        
        # Валюта по умолчанию
        currency = 'тг'
        
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {str(e)}")
        messages.warning(request, 'Произошла ошибка при загрузке статистики. Пожалуйста, попробуйте позже.')
        # Устанавливаем значения по умолчанию при ошибке
        new_leads_count = active_deals_count = won_deals_count = 0
        new_leads_diff = active_deals_diff = won_deals_diff = conversion_diff = 0
        active_deals_amount = won_deals_amount = 0
        conversion_rate = 0
        funnel_stages = funnel_counts = funnel_amounts = []
        lead_sources = lead_sources_counts = lead_sources_percentages = []
        recent_activities = recent_messages = upcoming_tasks = recent_deals = []
        currency = 'тг'
        today = timezone.now().date()
        active_campaigns = Campaign.objects.filter(
            status='active',
            start_date__lte=today,
            end_date__gte=today
        )[:5]
        
        if marketer and not is_admin:
            active_campaigns = active_campaigns.filter(manager=request.user)[:5]
    except Exception as e:
        logger.error(f"Ошибка при получении активных кампаний: {str(e)}")
        active_campaigns = []
    
    # Непрочитанные сообщения
    try:
        unread_messages = SocialMessage.objects.filter(is_read=False).count()
        if marketer and not is_admin:
            unread_messages = SocialMessage.objects.filter(is_read=False, assigned_to=request.user).count()
    except Exception as e:
        logger.error(f"Ошибка при получении непрочитанных сообщений: {str(e)}")
        unread_messages = 0
    
    # Формируем контекст для шаблона
    context = {
        # Ключевые показатели
        'new_leads_count': new_leads_count,
        'new_leads_diff': round(new_leads_diff, 1),
        'new_leads_percent': min(100, new_leads_count * 5),  # Для прогресс-бара
        'active_deals_count': active_deals_count,
        'active_deals_amount': active_deals_amount,
        'active_deals_diff': round(active_deals_diff, 1),
        'active_deals_percent': min(100, active_deals_count * 5),
        'won_deals_count': won_deals_count,
        'won_deals_amount': won_deals_amount,
        'won_deals_diff': round(won_deals_diff, 1),
        'won_deals_percent': min(100, won_deals_count * 5),
        'conversion_rate': round(conversion_rate, 1),
        'conversion_diff': 0,  # Пока нет данных для сравнения
        
        # Данные для графиков
        'funnel_stages': json.dumps(funnel_stages),
        'funnel_counts': json.dumps(funnel_counts),
        'funnel_amounts': json.dumps(funnel_amounts),
        'lead_sources': json.dumps(lead_sources),
        'lead_sources_counts': json.dumps(lead_sources_counts),
        'lead_sources_percentages': json.dumps(lead_sources_percentages),
        
        # Списки последних элементов
        'recent_activities': recent_activities,
        'recent_messages': recent_messages,
        'upcoming_tasks': upcoming_tasks,
        'recent_deals': recent_deals,
        
        # Дополнительные данные
        'currency': currency,
        'today': today.strftime('%Y-%m-%d'),
    }
    
    return render(request, 'crm/dashboard.html', context)

# Представления для работы с лидами
def lead_list(request):
    """Список всех лидов с возможностью фильтрации"""
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
    
    # Получаем параметры фильтрации
    status_filter = request.GET.get('status', '')
    source_filter = request.GET.get('source', '')
    search_query = request.GET.get('q', '')
    
    # Базовый запрос
    try:
        leads = Lead.objects.all().order_by('-created_at')
        
        # Если это маркетолог, показываем только его лидов
        if is_marketer and not is_admin:
            leads = leads.filter(assigned_to=request.user)
    except Exception as e:
        logger.error(f"Ошибка при получении лидов: {str(e)}")
        leads = Lead.objects.none()  # Возвращаем пустой QuerySet
    
    # Применяем фильтры
    if status_filter:
        leads = leads.filter(status=status_filter)
    
    if source_filter:
        leads = leads.filter(source_id=source_filter)
    
    if search_query:
        leads = leads.filter(
            Q(full_name__icontains=search_query) | 
            Q(phone_number__icontains=search_query) | 
            Q(email__icontains=search_query)
        )
    
    # Сортировка
    sort_by = request.GET.get('sort', '-created_at')
    leads = leads.order_by(sort_by)
    
    # Пагинация
    paginator = Paginator(leads, 20)  # 20 лидов на страницу
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Дополнительные данные для фильтров
    lead_sources = LeadSource.objects.filter(is_active=True)
    lead_statuses = dict(Lead.LEAD_STATUS_CHOICES)
    
    context = {
        'page_obj': page_obj,
        'lead_sources': lead_sources,
        'lead_statuses': lead_statuses,
        'status_filter': status_filter,
        'source_filter': source_filter,
        'search_query': search_query,
        'sort_by': sort_by,
    }
    
    return render(request, 'crm/lead_list.html', context)

@marketer_required
def lead_detail(request, lead_id):
    """Детальная информация о лиде с историей взаимодействий"""
    lead = get_object_or_404(Lead, pk=lead_id)
    
    # Проверка прав доступа к лиду
    if not request.user.is_admin and request.user.is_marketer and lead.assigned_to != request.user:
        messages.error(request, 'У вас нет прав для просмотра этого лида.')
        return redirect('crm:lead_list')
    
    # История статусов
    status_history = lead.status_history.all().order_by('-entered_at')
    
    # Взаимодействия
    interactions = lead.interactions.all().order_by('-date_time')
    
    # Сообщения из соцсетей
    social_messages = lead.social_messages.all().order_by('-timestamp')
    
    # Доступные этапы воронки
    sale_stages = SaleStage.objects.filter(is_active=True).order_by('order')
    
    # Доступные маркетологи
    marketers = User.objects.filter(user_type='marketer', is_active=True)
    
    context = {
        'lead': lead,
        'status_history': status_history,
        'interactions': interactions,
        'social_messages': social_messages,
        'sale_stages': sale_stages,
        'marketers': marketers,
        'lead_statuses': dict(Lead.LEAD_STATUS_CHOICES),
        'interaction_types': dict(Interaction.INTERACTION_TYPE_CHOICES),
        'interaction_results': dict(Interaction.INTERACTION_RESULT_CHOICES),
    }
    
    return render(request, 'crm/lead_detail.html', context)

@marketer_required
def lead_create(request):
    """Создание нового лида"""
    if request.method == 'POST':
        # Получаем данные из формы
        full_name = request.POST.get('full_name')
        phone_number = request.POST.get('phone_number')
        email = request.POST.get('email')
        source_id = request.POST.get('source')
        notes = request.POST.get('notes')
        
        # Дополнительные поля
        birth_date = request.POST.get('birth_date') or None
        school = request.POST.get('school')
        current_grade = request.POST.get('current_grade') or None
        parent_name = request.POST.get('parent_name')
        parent_phone = request.POST.get('parent_phone')
        interested_subjects = request.POST.get('interested_subjects')
        
        # Проверка обязательных полей
        if not full_name or not phone_number:
            messages.error(request, 'Пожалуйста, заполните все обязательные поля.')
            return redirect('crm:lead_create')
        
        try:
            # Создаем нового лида
            lead = Lead(
                full_name=full_name,
                phone_number=phone_number,
                email=email,
                source_id=source_id,
                notes=notes,
                birth_date=birth_date,
                school=school,
                current_grade=current_grade,
                parent_name=parent_name,
                parent_phone=parent_phone,
                interested_subjects=interested_subjects,
                assigned_to=request.user,  # Назначаем текущего пользователя
                status='new'  # Статус "Новый"
            )
            lead.save()
            
            messages.success(request, f'Лид {full_name} успешно создан!')
            return redirect('crm:lead_detail', lead_id=lead.id)
            
        except Exception as e:
            logger.error(f'Ошибка при создании лида: {str(e)}')
            messages.error(request, f'Ошибка при создании лида: {str(e)}')
    
    # Данные для формы
    lead_sources = LeadSource.objects.filter(is_active=True)
    
    context = {
        'lead_sources': lead_sources,
    }
    
    return render(request, 'crm/lead_form.html', context)

@marketer_required
def lead_update(request, lead_id):
    """Обновление информации о лиде"""
    lead = get_object_or_404(Lead, pk=lead_id)
    
    # Проверка прав доступа к лиду
    if not request.user.is_admin and request.user.is_marketer and lead.assigned_to != request.user:
        messages.error(request, 'У вас нет прав для редактирования этого лида.')
        return redirect('crm:lead_list')
    
    if request.method == 'POST':
        # Получаем данные из формы
        lead.full_name = request.POST.get('full_name')
        lead.phone_number = request.POST.get('phone_number')
        lead.email = request.POST.get('email')
        lead.source_id = request.POST.get('source')
        lead.notes = request.POST.get('notes')
        
        # Дополнительные поля
        birth_date = request.POST.get('birth_date')
        lead.birth_date = birth_date if birth_date else None
        lead.school = request.POST.get('school')
        current_grade = request.POST.get('current_grade')
        lead.current_grade = current_grade if current_grade else None
        lead.parent_name = request.POST.get('parent_name')
        lead.parent_phone = request.POST.get('parent_phone')
        lead.interested_subjects = request.POST.get('interested_subjects')
        
        # Статус и назначение
        new_status = request.POST.get('status')
        new_assigned_to_id = request.POST.get('assigned_to')
        
        # Проверка изменения статуса
        if new_status and new_status != lead.status:
            old_status = lead.status
            lead.status = new_status
            
            # Запись в историю изменений статуса
            status_note = f'Статус изменен с "{dict(Lead.LEAD_STATUS_CHOICES).get(old_status)}" на "{dict(Lead.LEAD_STATUS_CHOICES).get(new_status)}"'
            LeadStatusHistory.objects.create(
                lead=lead,
                stage=lead.current_stage,
                notes=status_note,
                changed_by=request.user
            )
        
        # Проверка изменения назначенного маркетолога
        if new_assigned_to_id and (not lead.assigned_to or str(lead.assigned_to.id) != new_assigned_to_id):
            lead.assigned_to = User.objects.get(pk=new_assigned_to_id)
        
        try:
            lead.save()
            messages.success(request, f'Информация о лиде {lead.full_name} успешно обновлена!')
            return redirect('crm:lead_detail', lead_id=lead.id)
            
        except Exception as e:
            logger.error(f'Ошибка при обновлении лида: {str(e)}')
            messages.error(request, f'Ошибка при обновлении лида: {str(e)}')
    
    # Данные для формы
    lead_sources = LeadSource.objects.filter(is_active=True)
    marketers = User.objects.filter(user_type='marketer', is_active=True)
    
    context = {
        'lead': lead,
        'lead_sources': lead_sources,
        'marketers': marketers,
        'lead_statuses': dict(Lead.LEAD_STATUS_CHOICES),
        'is_update': True,
    }
    
    return render(request, 'crm/lead_form.html', context)

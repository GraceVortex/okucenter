import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, Count, F, Value, Case, When, DecimalField
from django.db.models.functions import Coalesce
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.utils import timezone
from .models_new import Deal, Pipeline, Stage, Contact, Company
from .forms import DealForm  # Форму нужно будет создать

logger = logging.getLogger(__name__)

@login_required
def deal_list(request):
    """
    Отображение списка сделок с фильтрацией и поиском
    """
    # Получаем параметры фильтрации
    pipeline_id = request.GET.get('pipeline', '')
    stage_id = request.GET.get('stage', '')
    status = request.GET.get('status', '')
    search_query = request.GET.get('q', '')
    
    # Базовый запрос
    deals_query = Deal.objects.all()
    
    # Применяем фильтры
    if pipeline_id:
        deals_query = deals_query.filter(pipeline_id=pipeline_id)
    
    if stage_id:
        deals_query = deals_query.filter(stage_id=stage_id)
    
    if status:
        deals_query = deals_query.filter(status=status)
    
    # Применяем поиск
    if search_query:
        deals_query = deals_query.filter(
            Q(title__icontains=search_query) |
            Q(contact__first_name__icontains=search_query) |
            Q(contact__last_name__icontains=search_query) |
            Q(company__name__icontains=search_query)
        )
    
    # Сортировка
    deals_query = deals_query.order_by('-created_at')
    
    # Пагинация
    paginator = Paginator(deals_query, 25)  # 25 сделок на страницу
    page_number = request.GET.get('page', 1)
    deals = paginator.get_page(page_number)
    
    # Получаем списки для фильтров
    pipelines = Pipeline.objects.filter(is_active=True).order_by('name')
    stages = Stage.objects.filter(is_active=True)
    if pipeline_id:
        stages = stages.filter(pipeline_id=pipeline_id)
    stages = stages.order_by('pipeline', 'order')
    
    # Подготавливаем контекст
    context = {
        'deals': deals,
        'pipelines': pipelines,
        'stages': stages,
        'selected_pipeline': pipeline_id,
        'selected_stage': stage_id,
        'selected_status': status,
        'search_query': search_query,
        'status_choices': Deal.DEAL_STATUS_CHOICES,
        'total_deals': deals_query.count(),
        'total_amount': deals_query.aggregate(total=Coalesce(Sum('amount'), 0))['total'],
    }
    
    return render(request, 'crm/deal_list.html', context)

@login_required
def deal_kanban(request):
    """
    Отображение сделок в виде канбан-доски
    """
    # Получаем параметры фильтрации
    pipeline_id = request.GET.get('pipeline', '')
    status = request.GET.get('status', 'open')  # По умолчанию показываем только открытые сделки
    search_query = request.GET.get('q', '')
    
    # Если pipeline_id не указан, берем первый активный pipeline
    if not pipeline_id:
        default_pipeline = Pipeline.objects.filter(is_active=True).first()
        if default_pipeline:
            pipeline_id = default_pipeline.id
    
    # Получаем pipeline и его этапы
    pipeline = None
    stages = []
    
    if pipeline_id:
        pipeline = get_object_or_404(Pipeline, id=pipeline_id, is_active=True)
        stages = pipeline.stages.filter(is_active=True).order_by('order')
    
    # Базовый запрос для сделок
    deals_query = Deal.objects.filter(status=status)
    
    if pipeline:
        deals_query = deals_query.filter(pipeline=pipeline)
    
    # Применяем поиск
    if search_query:
        deals_query = deals_query.filter(
            Q(title__icontains=search_query) |
            Q(contact__first_name__icontains=search_query) |
            Q(contact__last_name__icontains=search_query) |
            Q(company__name__icontains=search_query)
        )
    
    # Группируем сделки по этапам
    deals_by_stage = {}
    for stage in stages:
        stage_deals = deals_query.filter(stage=stage).order_by('-created_at')
        deals_by_stage[stage.id] = stage_deals
    
    # Получаем списки для фильтров
    pipelines = Pipeline.objects.filter(is_active=True).order_by('name')
    
    # Подготавливаем контекст
    context = {
        'pipeline': pipeline,
        'stages': stages,
        'deals_by_stage': deals_by_stage,
        'pipelines': pipelines,
        'selected_pipeline': pipeline_id if pipeline else '',
        'selected_status': status,
        'search_query': search_query,
        'status_choices': Deal.DEAL_STATUS_CHOICES,
    }
    
    return render(request, 'crm/deal_kanban.html', context)

@login_required
def deal_detail(request, deal_id):
    """
    Отображение детальной информации о сделке
    """
    deal = get_object_or_404(Deal, id=deal_id)
    
    # Получаем активности
    activities = []  # Здесь будут активности, связанные со сделкой
    
    context = {
        'deal': deal,
        'activities': activities,
    }
    
    return render(request, 'crm/deal_detail.html', context)

@login_required
def deal_create(request):
    """
    Создание новой сделки
    """
    # Получаем параметры для предзаполнения формы
    contact_id = request.GET.get('contact', '')
    company_id = request.GET.get('company', '')
    pipeline_id = request.GET.get('pipeline', '')
    
    initial_data = {}
    
    # Если указан контакт, предзаполняем поле контакта
    if contact_id:
        try:
            contact = Contact.objects.get(id=contact_id)
            initial_data['contact'] = contact
            
            # Если у контакта есть компания, предзаполняем поле компании
            if contact.company:
                initial_data['company'] = contact.company
        except Contact.DoesNotExist:
            pass
    
    # Если указана компания, предзаполняем поле компании
    if company_id and 'company' not in initial_data:
        try:
            company = Company.objects.get(id=company_id)
            initial_data['company'] = company
        except Company.DoesNotExist:
            pass
    
    # Если указан pipeline, предзаполняем поле pipeline и устанавливаем первый этап
    if pipeline_id:
        try:
            pipeline = Pipeline.objects.get(id=pipeline_id)
            initial_data['pipeline'] = pipeline
            
            # Получаем первый этап воронки
            first_stage = pipeline.stages.filter(is_active=True).order_by('order').first()
            if first_stage:
                initial_data['stage'] = first_stage
        except Pipeline.DoesNotExist:
            pass
    
    if request.method == 'POST':
        form = DealForm(request.POST)
        if form.is_valid():
            deal = form.save(commit=False)
            deal.responsible = request.user  # Устанавливаем текущего пользователя как ответственного
            deal.save()
            messages.success(request, f'Сделка "{deal.title}" успешно создана')
            return redirect('deal_detail', deal_id=deal.id)
    else:
        form = DealForm(initial=initial_data)
    
    context = {
        'form': form,
        'title': 'Создание сделки',
    }
    
    return render(request, 'crm/deal_form.html', context)

@login_required
def deal_update(request, deal_id):
    """
    Обновление существующей сделки
    """
    deal = get_object_or_404(Deal, id=deal_id)
    
    if request.method == 'POST':
        form = DealForm(request.POST, instance=deal)
        if form.is_valid():
            # Проверяем, изменился ли статус сделки
            old_status = deal.status
            new_status = form.cleaned_data['status']
            
            deal = form.save()
            
            # Если статус изменился на 'won' или 'lost', устанавливаем дату закрытия
            if old_status != new_status and new_status in ['won', 'lost'] and not deal.closed_at:
                deal.closed_at = timezone.now()
                deal.save()
            
            messages.success(request, f'Сделка "{deal.title}" успешно обновлена')
            return redirect('deal_detail', deal_id=deal.id)
    else:
        form = DealForm(instance=deal)
    
    context = {
        'form': form,
        'deal': deal,
        'title': 'Редактирование сделки',
    }
    
    return render(request, 'crm/deal_form.html', context)

@login_required
def deal_delete(request, deal_id):
    """
    Удаление сделки
    """
    deal = get_object_or_404(Deal, id=deal_id)
    
    if request.method == 'POST':
        deal_title = deal.title
        deal.delete()
        messages.success(request, f'Сделка "{deal_title}" успешно удалена')
        return redirect('deal_list')
    
    context = {
        'deal': deal,
    }
    
    return render(request, 'crm/deal_confirm_delete.html', context)

@login_required
def deal_change_stage(request):
    """
    AJAX-представление для изменения этапа сделки (для канбан-доски)
    """
    if request.method == 'POST' and request.is_ajax():
        deal_id = request.POST.get('deal_id')
        stage_id = request.POST.get('stage_id')
        
        try:
            deal = Deal.objects.get(id=deal_id)
            stage = Stage.objects.get(id=stage_id)
            
            # Проверяем, что этап принадлежит той же воронке, что и сделка
            if deal.pipeline != stage.pipeline:
                return JsonResponse({'success': False, 'error': 'Stage does not belong to the deal pipeline'})
            
            # Обновляем этап сделки
            deal.stage = stage
            deal.save()
            
            return JsonResponse({'success': True})
        except (Deal.DoesNotExist, Stage.DoesNotExist):
            return JsonResponse({'success': False, 'error': 'Deal or Stage not found'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def pipeline_list(request):
    """
    Отображение списка воронок продаж
    """
    pipelines = Pipeline.objects.all().order_by('name')
    
    context = {
        'pipelines': pipelines,
    }
    
    return render(request, 'crm/pipeline_list.html', context)

@login_required
def pipeline_detail(request, pipeline_id):
    """
    Отображение детальной информации о воронке продаж
    """
    pipeline = get_object_or_404(Pipeline, id=pipeline_id)
    stages = pipeline.stages.all().order_by('order')
    
    # Получаем статистику по сделкам в каждом этапе
    stages_with_stats = []
    for stage in stages:
        stage_deals = Deal.objects.filter(pipeline=pipeline, stage=stage, status='open')
        stage_stats = {
            'stage': stage,
            'deals_count': stage_deals.count(),
            'total_amount': stage_deals.aggregate(total=Coalesce(Sum('amount'), 0))['total'],
        }
        stages_with_stats.append(stage_stats)
    
    context = {
        'pipeline': pipeline,
        'stages': stages_with_stats,
    }
    
    return render(request, 'crm/pipeline_detail.html', context)

import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from .models_activities import Activity, Task, Call, Meeting, Email, Note
from .models_new import Contact, Company, Deal
from .forms import ActivityForm, TaskForm, CallForm, MeetingForm, EmailForm, NoteForm  # Формы нужно будет создать

logger = logging.getLogger(__name__)

@login_required
def activity_list(request):
    """
    Отображение списка активностей с фильтрацией и поиском
    """
    # Получаем параметры фильтрации
    activity_type = request.GET.get('type', '')
    status = request.GET.get('status', '')
    search_query = request.GET.get('q', '')
    
    # Базовый запрос
    activities_query = Activity.objects.all()
    
    # Применяем фильтры
    if activity_type:
        activities_query = activities_query.filter(activity_type=activity_type)
    
    if status:
        activities_query = activities_query.filter(status=status)
    
    # Применяем поиск
    if search_query:
        activities_query = activities_query.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Сортировка
    activities_query = activities_query.order_by('-due_date', '-created_at')
    
    # Пагинация
    paginator = Paginator(activities_query, 25)  # 25 активностей на страницу
    page_number = request.GET.get('page', 1)
    activities = paginator.get_page(page_number)
    
    # Подготавливаем контекст
    context = {
        'activities': activities,
        'activity_type': activity_type,
        'status': status,
        'search_query': search_query,
        'activity_type_choices': Activity.ACTIVITY_TYPE_CHOICES,
        'status_choices': Activity.STATUS_CHOICES,
        'total_activities': activities_query.count(),
    }
    
    return render(request, 'crm/activity_list.html', context)

@login_required
def activity_calendar(request):
    """
    Отображение активностей в виде календаря
    """
    # Получаем параметры фильтрации
    activity_type = request.GET.get('type', '')
    status = request.GET.get('status', '')
    
    # Базовый запрос
    activities_query = Activity.objects.all()
    
    # Применяем фильтры
    if activity_type:
        activities_query = activities_query.filter(activity_type=activity_type)
    
    if status:
        activities_query = activities_query.filter(status=status)
    
    # Получаем только активности с датой
    activities_query = activities_query.exclude(due_date__isnull=True)
    
    # Преобразуем активности в формат для календаря
    calendar_events = []
    for activity in activities_query:
        event = {
            'id': activity.id,
            'title': activity.title,
            'start': activity.due_date.isoformat(),
            'end': activity.end_date.isoformat() if activity.end_date else None,
            'url': f'/crm/activities/{activity.id}/',
            'backgroundColor': get_activity_color(activity),
        }
        calendar_events.append(event)
    
    # Подготавливаем контекст
    context = {
        'calendar_events': calendar_events,
        'activity_type': activity_type,
        'status': status,
        'activity_type_choices': Activity.ACTIVITY_TYPE_CHOICES,
        'status_choices': Activity.STATUS_CHOICES,
    }
    
    return render(request, 'crm/activity_calendar.html', context)

def get_activity_color(activity):
    """
    Возвращает цвет для активности в зависимости от типа и приоритета
    """
    # Цвета для типов активностей
    type_colors = {
        'task': '#3498db',  # Синий
        'call': '#2ecc71',  # Зеленый
        'meeting': '#9b59b6',  # Фиолетовый
        'email': '#e74c3c',  # Красный
        'note': '#f39c12',  # Оранжевый
        'other': '#95a5a6',  # Серый
    }
    
    # Цвета для приоритетов
    priority_colors = {
        'low': '#3498db',  # Синий
        'medium': '#f39c12',  # Оранжевый
        'high': '#e74c3c',  # Красный
        'urgent': '#c0392b',  # Темно-красный
    }
    
    # По умолчанию используем цвет типа активности
    color = type_colors.get(activity.activity_type, '#95a5a6')
    
    # Для задач с высоким приоритетом используем цвет приоритета
    if activity.activity_type == 'task' and activity.priority in ['high', 'urgent']:
        color = priority_colors.get(activity.priority, color)
    
    return color

@login_required
def activity_detail(request, activity_id):
    """
    Отображение детальной информации об активности
    """
    activity = get_object_or_404(Activity, id=activity_id)
    
    # Определяем тип активности и получаем соответствующий объект
    activity_obj = activity
    if activity.activity_type == 'task':
        try:
            activity_obj = Task.objects.get(id=activity.id)
        except Task.DoesNotExist:
            pass
    elif activity.activity_type == 'call':
        try:
            activity_obj = Call.objects.get(id=activity.id)
        except Call.DoesNotExist:
            pass
    elif activity.activity_type == 'meeting':
        try:
            activity_obj = Meeting.objects.get(id=activity.id)
        except Meeting.DoesNotExist:
            pass
    elif activity.activity_type == 'email':
        try:
            activity_obj = Email.objects.get(id=activity.id)
        except Email.DoesNotExist:
            pass
    elif activity.activity_type == 'note':
        try:
            activity_obj = Note.objects.get(id=activity.id)
        except Note.DoesNotExist:
            pass
    
    # Получаем связанный объект (контакт, компания, сделка)
    related_object = None
    if activity.content_type and activity.object_id:
        try:
            related_object = activity.related_object
        except:
            pass
    
    context = {
        'activity': activity_obj,
        'related_object': related_object,
    }
    
    return render(request, 'crm/activity_detail.html', context)

@login_required
def task_create(request):
    """
    Создание новой задачи
    """
    # Получаем параметры для связанного объекта
    content_type_id = request.GET.get('content_type_id', '')
    object_id = request.GET.get('object_id', '')
    
    initial_data = {
        'activity_type': 'task',
        'created_by': request.user,
        'assigned_to': request.user,
    }
    
    # Если указан связанный объект, предзаполняем поля content_type и object_id
    if content_type_id and object_id:
        try:
            content_type = ContentType.objects.get(id=content_type_id)
            initial_data['content_type'] = content_type
            initial_data['object_id'] = object_id
        except ContentType.DoesNotExist:
            pass
    
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            task.save()
            messages.success(request, f'Задача "{task.title}" успешно создана')
            
            # Если есть связанный объект, перенаправляем на его страницу
            if task.content_type and task.object_id:
                try:
                    related_object = task.related_object
                    if isinstance(related_object, Contact):
                        return redirect('contact_detail', contact_id=related_object.id)
                    elif isinstance(related_object, Company):
                        return redirect('company_detail', company_id=related_object.id)
                    elif isinstance(related_object, Deal):
                        return redirect('deal_detail', deal_id=related_object.id)
                except:
                    pass
            
            return redirect('activity_detail', activity_id=task.id)
    else:
        form = TaskForm(initial=initial_data)
    
    context = {
        'form': form,
        'title': 'Создание задачи',
    }
    
    return render(request, 'crm/task_form.html', context)

@login_required
def call_create(request):
    """
    Создание нового звонка
    """
    # Получаем параметры для связанного объекта
    content_type_id = request.GET.get('content_type_id', '')
    object_id = request.GET.get('object_id', '')
    
    initial_data = {
        'activity_type': 'call',
        'created_by': request.user,
        'assigned_to': request.user,
    }
    
    # Если указан связанный объект, предзаполняем поля content_type и object_id
    if content_type_id and object_id:
        try:
            content_type = ContentType.objects.get(id=content_type_id)
            initial_data['content_type'] = content_type
            initial_data['object_id'] = object_id
            
            # Если связанный объект - контакт, предзаполняем номер телефона
            try:
                related_object = content_type.get_object_for_this_type(id=object_id)
                if isinstance(related_object, Contact) and related_object.phone:
                    initial_data['phone_number'] = related_object.phone
            except:
                pass
        except ContentType.DoesNotExist:
            pass
    
    if request.method == 'POST':
        form = CallForm(request.POST)
        if form.is_valid():
            call = form.save(commit=False)
            call.created_by = request.user
            call.save()
            messages.success(request, f'Звонок "{call.title}" успешно создан')
            
            # Если есть связанный объект, перенаправляем на его страницу
            if call.content_type and call.object_id:
                try:
                    related_object = call.related_object
                    if isinstance(related_object, Contact):
                        return redirect('contact_detail', contact_id=related_object.id)
                    elif isinstance(related_object, Company):
                        return redirect('company_detail', company_id=related_object.id)
                    elif isinstance(related_object, Deal):
                        return redirect('deal_detail', deal_id=related_object.id)
                except:
                    pass
            
            return redirect('activity_detail', activity_id=call.id)
    else:
        form = CallForm(initial=initial_data)
    
    context = {
        'form': form,
        'title': 'Создание звонка',
    }
    
    return render(request, 'crm/call_form.html', context)

@login_required
def meeting_create(request):
    """
    Создание новой встречи
    """
    # Получаем параметры для связанного объекта
    content_type_id = request.GET.get('content_type_id', '')
    object_id = request.GET.get('object_id', '')
    
    initial_data = {
        'activity_type': 'meeting',
        'created_by': request.user,
        'assigned_to': request.user,
    }
    
    # Если указан связанный объект, предзаполняем поля content_type и object_id
    if content_type_id and object_id:
        try:
            content_type = ContentType.objects.get(id=content_type_id)
            initial_data['content_type'] = content_type
            initial_data['object_id'] = object_id
        except ContentType.DoesNotExist:
            pass
    
    if request.method == 'POST':
        form = MeetingForm(request.POST)
        if form.is_valid():
            meeting = form.save(commit=False)
            meeting.created_by = request.user
            meeting.save()
            
            # Сохраняем участников встречи
            if 'participants' in form.cleaned_data:
                meeting.participants.set(form.cleaned_data['participants'])
            
            messages.success(request, f'Встреча "{meeting.title}" успешно создана')
            
            # Если есть связанный объект, перенаправляем на его страницу
            if meeting.content_type and meeting.object_id:
                try:
                    related_object = meeting.related_object
                    if isinstance(related_object, Contact):
                        return redirect('contact_detail', contact_id=related_object.id)
                    elif isinstance(related_object, Company):
                        return redirect('company_detail', company_id=related_object.id)
                    elif isinstance(related_object, Deal):
                        return redirect('deal_detail', deal_id=related_object.id)
                except:
                    pass
            
            return redirect('activity_detail', activity_id=meeting.id)
    else:
        form = MeetingForm(initial=initial_data)
    
    context = {
        'form': form,
        'title': 'Создание встречи',
    }
    
    return render(request, 'crm/meeting_form.html', context)

@login_required
def activity_update(request, activity_id):
    """
    Обновление существующей активности
    """
    activity = get_object_or_404(Activity, id=activity_id)
    
    # Определяем тип активности и получаем соответствующий объект и форму
    if activity.activity_type == 'task':
        try:
            activity_obj = Task.objects.get(id=activity.id)
            form_class = TaskForm
            template = 'crm/task_form.html'
        except Task.DoesNotExist:
            activity_obj = activity
            form_class = ActivityForm
            template = 'crm/activity_form.html'
    elif activity.activity_type == 'call':
        try:
            activity_obj = Call.objects.get(id=activity.id)
            form_class = CallForm
            template = 'crm/call_form.html'
        except Call.DoesNotExist:
            activity_obj = activity
            form_class = ActivityForm
            template = 'crm/activity_form.html'
    elif activity.activity_type == 'meeting':
        try:
            activity_obj = Meeting.objects.get(id=activity.id)
            form_class = MeetingForm
            template = 'crm/meeting_form.html'
        except Meeting.DoesNotExist:
            activity_obj = activity
            form_class = ActivityForm
            template = 'crm/activity_form.html'
    elif activity.activity_type == 'email':
        try:
            activity_obj = Email.objects.get(id=activity.id)
            form_class = EmailForm
            template = 'crm/email_form.html'
        except Email.DoesNotExist:
            activity_obj = activity
            form_class = ActivityForm
            template = 'crm/activity_form.html'
    elif activity.activity_type == 'note':
        try:
            activity_obj = Note.objects.get(id=activity.id)
            form_class = NoteForm
            template = 'crm/note_form.html'
        except Note.DoesNotExist:
            activity_obj = activity
            form_class = ActivityForm
            template = 'crm/activity_form.html'
    else:
        activity_obj = activity
        form_class = ActivityForm
        template = 'crm/activity_form.html'
    
    if request.method == 'POST':
        form = form_class(request.POST, instance=activity_obj)
        if form.is_valid():
            activity_obj = form.save()
            
            # Если это встреча, сохраняем участников
            if activity.activity_type == 'meeting' and hasattr(activity_obj, 'participants'):
                if 'participants' in form.cleaned_data:
                    activity_obj.participants.set(form.cleaned_data['participants'])
            
            messages.success(request, f'Активность "{activity_obj.title}" успешно обновлена')
            return redirect('activity_detail', activity_id=activity_obj.id)
    else:
        form = form_class(instance=activity_obj)
    
    context = {
        'form': form,
        'activity': activity_obj,
        'title': f'Редактирование {activity_obj.get_activity_type_display().lower()}',
    }
    
    return render(request, template, context)

@login_required
def activity_delete(request, activity_id):
    """
    Удаление активности
    """
    activity = get_object_or_404(Activity, id=activity_id)
    
    # Сохраняем информацию о связанном объекте для перенаправления после удаления
    related_object = None
    if activity.content_type and activity.object_id:
        try:
            related_object = activity.related_object
        except:
            pass
    
    if request.method == 'POST':
        activity_title = activity.title
        activity.delete()
        messages.success(request, f'Активность "{activity_title}" успешно удалена')
        
        # Если есть связанный объект, перенаправляем на его страницу
        if related_object:
            if isinstance(related_object, Contact):
                return redirect('contact_detail', contact_id=related_object.id)
            elif isinstance(related_object, Company):
                return redirect('company_detail', company_id=related_object.id)
            elif isinstance(related_object, Deal):
                return redirect('deal_detail', deal_id=related_object.id)
        
        return redirect('activity_list')
    
    context = {
        'activity': activity,
    }
    
    return render(request, 'crm/activity_confirm_delete.html', context)

@login_required
def activity_complete(request, activity_id):
    """
    Отметка активности как выполненной
    """
    activity = get_object_or_404(Activity, id=activity_id)
    
    activity.status = 'completed'
    activity.completed_date = timezone.now()
    activity.save()
    
    messages.success(request, f'Активность "{activity.title}" отмечена как выполненная')
    
    # Перенаправляем на предыдущую страницу
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    
    return redirect('activity_detail', activity_id=activity.id)

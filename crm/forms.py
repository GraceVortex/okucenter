from django import forms
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from .models_new import Contact, Company, Deal, Pipeline, Stage
from .models_activities import Activity, Task, Call, Meeting, Email, Note
from accounts.models import User

class ContactForm(forms.ModelForm):
    """
    Форма для создания и редактирования контактов
    """
    class Meta:
        model = Contact
        fields = [
            'first_name', 'last_name', 'middle_name', 'contact_type',
            'phone', 'email', 'position', 'company', 'responsible', 'notes'
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавляем классы Bootstrap для полей
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        
        # Фильтруем список ответственных (только активные пользователи)
        self.fields['responsible'].queryset = User.objects.filter(is_active=True)

class CompanyForm(forms.ModelForm):
    """
    Форма для создания и редактирования компаний
    """
    class Meta:
        model = Company
        fields = [
            'name', 'company_type', 'website', 'phone', 'email',
            'address', 'description', 'responsible'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавляем классы Bootstrap для полей
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        
        # Фильтруем список ответственных (только активные пользователи)
        self.fields['responsible'].queryset = User.objects.filter(is_active=True)

class DealForm(forms.ModelForm):
    """
    Форма для создания и редактирования сделок
    """
    class Meta:
        model = Deal
        fields = [
            'title', 'pipeline', 'stage', 'status', 'contact', 'company',
            'amount', 'currency', 'expected_close_date', 'responsible', 'description'
        ]
        widgets = {
            'expected_close_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавляем классы Bootstrap для полей
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        
        # Фильтруем список ответственных (только активные пользователи)
        self.fields['responsible'].queryset = User.objects.filter(is_active=True)
        
        # Фильтруем список этапов в зависимости от выбранной воронки
        if 'pipeline' in self.data:
            try:
                pipeline_id = int(self.data.get('pipeline'))
                self.fields['stage'].queryset = Stage.objects.filter(
                    pipeline_id=pipeline_id, is_active=True
                ).order_by('order')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.pipeline:
            self.fields['stage'].queryset = Stage.objects.filter(
                pipeline=self.instance.pipeline, is_active=True
            ).order_by('order')
        else:
            self.fields['stage'].queryset = Stage.objects.none()

class ActivityForm(forms.ModelForm):
    """
    Базовая форма для активностей
    """
    class Meta:
        model = Activity
        fields = [
            'title', 'description', 'activity_type', 'priority', 'status',
            'due_date', 'start_date', 'end_date', 'assigned_to',
            'content_type', 'object_id'
        ]
        widgets = {
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавляем классы Bootstrap для полей
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        
        # Фильтруем список ответственных (только активные пользователи)
        self.fields['assigned_to'].queryset = User.objects.filter(is_active=True)
        
        # Скрываем поля content_type и object_id (они будут заполняться через GET-параметры)
        self.fields['content_type'].widget = forms.HiddenInput()
        self.fields['object_id'].widget = forms.HiddenInput()
        
        # Ограничиваем выбор content_type только нужными моделями
        valid_content_types = ContentType.objects.get_for_models(Contact, Company, Deal)
        self.fields['content_type'].queryset = ContentType.objects.filter(
            id__in=[ct.id for ct in valid_content_types.values()]
        )

class TaskForm(ActivityForm):
    """
    Форма для создания и редактирования задач
    """
    class Meta(ActivityForm.Meta):
        model = Task
        fields = ActivityForm.Meta.fields + ['reminder_date', 'is_recurring', 'recurrence_pattern']
        widgets = {
            **ActivityForm.Meta.widgets,
            'reminder_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Устанавливаем тип активности "Задача" и блокируем изменение
        self.fields['activity_type'].initial = 'task'
        self.fields['activity_type'].widget.attrs['readonly'] = True

class CallForm(ActivityForm):
    """
    Форма для создания и редактирования звонков
    """
    class Meta(ActivityForm.Meta):
        model = Call
        fields = ActivityForm.Meta.fields + ['phone_number', 'direction', 'duration', 'call_result', 'recording_url']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Устанавливаем тип активности "Звонок" и блокируем изменение
        self.fields['activity_type'].initial = 'call'
        self.fields['activity_type'].widget.attrs['readonly'] = True

class MeetingForm(ActivityForm):
    """
    Форма для создания и редактирования встреч
    """
    class Meta(ActivityForm.Meta):
        model = Meeting
        fields = ActivityForm.Meta.fields + ['location', 'is_online', 'meeting_url', 'participants']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Устанавливаем тип активности "Встреча" и блокируем изменение
        self.fields['activity_type'].initial = 'meeting'
        self.fields['activity_type'].widget.attrs['readonly'] = True
        
        # Настраиваем поле participants
        self.fields['participants'].queryset = User.objects.filter(is_active=True)
        self.fields['participants'].widget = forms.SelectMultiple(attrs={'class': 'form-control select2'})

class EmailForm(ActivityForm):
    """
    Форма для создания и редактирования email
    """
    class Meta(ActivityForm.Meta):
        model = Email
        fields = ActivityForm.Meta.fields + ['sender', 'recipient', 'cc', 'bcc', 'subject', 'body', 'is_html']
        widgets = {
            **ActivityForm.Meta.widgets,
            'body': forms.Textarea(attrs={'rows': 5}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Устанавливаем тип активности "Email" и блокируем изменение
        self.fields['activity_type'].initial = 'email'
        self.fields['activity_type'].widget.attrs['readonly'] = True

class NoteForm(ActivityForm):
    """
    Форма для создания и редактирования заметок
    """
    class Meta(ActivityForm.Meta):
        model = Note
        fields = ActivityForm.Meta.fields + ['text']
        widgets = {
            **ActivityForm.Meta.widgets,
            'text': forms.Textarea(attrs={'rows': 5}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Устанавливаем тип активности "Заметка" и блокируем изменение
        self.fields['activity_type'].initial = 'note'
        self.fields['activity_type'].widget.attrs['readonly'] = True

# Формы для аналитики
class ReportForm(forms.Form):
    """
    Форма для создания и настройки отчетов
    """
    REPORT_TYPE_CHOICES = (
        ('sales', 'Продажи'),
        ('leads', 'Лиды'),
        ('activities', 'Активности'),
        ('conversion', 'Конверсия'),
        ('custom', 'Пользовательский'),
    )
    
    name = forms.CharField(max_length=100, label='Название отчета')
    report_type = forms.ChoiceField(choices=REPORT_TYPE_CHOICES, label='Тип отчета')
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False, label='Описание')
    
    # Параметры для фильтрации данных
    date_from = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False, label='Дата с')
    date_to = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False, label='Дата по')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавляем классы Bootstrap для полей
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        
        # Устанавливаем значения по умолчанию для дат
        if not self.initial.get('date_from'):
            # По умолчанию - начало текущего месяца
            today = timezone.now().date()
            self.initial['date_from'] = today.replace(day=1)
        
        if not self.initial.get('date_to'):
            # По умолчанию - сегодня
            self.initial['date_to'] = timezone.now().date()

# Формы для интеграций
class WebhookForm(forms.Form):
    """
    Форма для настройки вебхуков для интеграций
    """
    name = forms.CharField(max_length=100, label='Название')
    url = forms.URLField(label='URL вебхука')
    secret_key = forms.CharField(max_length=100, required=False, label='Секретный ключ')
    is_active = forms.BooleanField(initial=True, required=False, label='Активен')
    
    # События, на которые реагирует вебхук
    events = forms.MultipleChoiceField(
        choices=[
            ('contact_created', 'Создание контакта'),
            ('contact_updated', 'Обновление контакта'),
            ('company_created', 'Создание компании'),
            ('company_updated', 'Обновление компании'),
            ('deal_created', 'Создание сделки'),
            ('deal_updated', 'Обновление сделки'),
            ('deal_stage_changed', 'Изменение этапа сделки'),
            ('activity_created', 'Создание активности'),
            ('activity_completed', 'Завершение активности'),
        ],
        widget=forms.CheckboxSelectMultiple,
        label='События'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавляем классы Bootstrap для полей
        for field_name, field in self.fields.items():
            if field_name != 'events':  # Для чекбоксов не добавляем класс form-control
                field.widget.attrs['class'] = 'form-control'

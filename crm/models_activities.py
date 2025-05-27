import logging
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from accounts.models import User

logger = logging.getLogger(__name__)

class Activity(models.Model):
    """
    Базовая модель для всех активностей (задачи, события, звонки и т.д.)
    """
    ACTIVITY_TYPE_CHOICES = (
        ('task', 'Задача'),
        ('call', 'Звонок'),
        ('meeting', 'Встреча'),
        ('email', 'Email'),
        ('note', 'Заметка'),
        ('other', 'Другое'),
    )
    
    PRIORITY_CHOICES = (
        ('low', 'Низкий'),
        ('medium', 'Средний'),
        ('high', 'Высокий'),
        ('urgent', 'Срочный'),
    )
    
    STATUS_CHOICES = (
        ('not_started', 'Не начато'),
        ('in_progress', 'В процессе'),
        ('completed', 'Завершено'),
        ('deferred', 'Отложено'),
        ('cancelled', 'Отменено'),
    )
    
    title = models.CharField(max_length=200, verbose_name="Заголовок")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPE_CHOICES, verbose_name="Тип активности")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium', verbose_name="Приоритет")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started', verbose_name="Статус")
    
    # Даты
    due_date = models.DateTimeField(blank=True, null=True, verbose_name="Срок выполнения")
    start_date = models.DateTimeField(blank=True, null=True, verbose_name="Дата начала")
    end_date = models.DateTimeField(blank=True, null=True, verbose_name="Дата окончания")
    completed_date = models.DateTimeField(blank=True, null=True, verbose_name="Дата выполнения")
    
    # Связь с пользователями
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_activities", 
                                  verbose_name="Создал")
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name="assigned_activities", verbose_name="Ответственный")
    
    # Связь с любой моделью (контакт, компания, сделка и т.д.)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, blank=True, null=True)
    object_id = models.PositiveIntegerField(blank=True, null=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Активность"
        verbose_name_plural = "Активности"
        ordering = ['-due_date', '-created_at']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        """
        Переопределяем метод save для установки даты выполнения при изменении статуса
        """
        if self.status == 'completed' and not self.completed_date:
            self.completed_date = timezone.now()
        super().save(*args, **kwargs)

class Task(Activity):
    """
    Модель для задач
    """
    # Дополнительные поля для задач
    reminder_date = models.DateTimeField(blank=True, null=True, verbose_name="Дата напоминания")
    is_recurring = models.BooleanField(default=False, verbose_name="Повторяющаяся задача")
    recurrence_pattern = models.CharField(max_length=100, blank=True, null=True, verbose_name="Шаблон повторения")
    
    class Meta:
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"

class Call(Activity):
    """
    Модель для звонков
    """
    CALL_DIRECTION_CHOICES = (
        ('incoming', 'Входящий'),
        ('outgoing', 'Исходящий'),
    )
    
    CALL_RESULT_CHOICES = (
        ('answered', 'Отвечен'),
        ('not_answered', 'Не отвечен'),
        ('busy', 'Занято'),
        ('wrong_number', 'Неверный номер'),
        ('voicemail', 'Голосовая почта'),
    )
    
    # Дополнительные поля для звонков
    phone_number = models.CharField(max_length=20, verbose_name="Номер телефона")
    direction = models.CharField(max_length=20, choices=CALL_DIRECTION_CHOICES, verbose_name="Направление")
    duration = models.PositiveIntegerField(default=0, verbose_name="Длительность (сек)")
    call_result = models.CharField(max_length=20, choices=CALL_RESULT_CHOICES, blank=True, null=True, 
                                  verbose_name="Результат звонка")
    recording_url = models.URLField(blank=True, null=True, verbose_name="URL записи разговора")
    
    class Meta:
        verbose_name = "Звонок"
        verbose_name_plural = "Звонки"

class Meeting(Activity):
    """
    Модель для встреч
    """
    # Дополнительные поля для встреч
    location = models.CharField(max_length=200, blank=True, null=True, verbose_name="Место проведения")
    is_online = models.BooleanField(default=False, verbose_name="Онлайн встреча")
    meeting_url = models.URLField(blank=True, null=True, verbose_name="URL встречи")
    
    # Участники встречи
    participants = models.ManyToManyField(User, related_name="meetings", blank=True, verbose_name="Участники")
    
    class Meta:
        verbose_name = "Встреча"
        verbose_name_plural = "Встречи"

class Email(Activity):
    """
    Модель для электронных писем
    """
    # Дополнительные поля для писем
    sender = models.EmailField(verbose_name="Отправитель")
    recipient = models.EmailField(verbose_name="Получатель")
    cc = models.TextField(blank=True, null=True, verbose_name="Копия")
    bcc = models.TextField(blank=True, null=True, verbose_name="Скрытая копия")
    subject = models.CharField(max_length=200, verbose_name="Тема")
    body = models.TextField(verbose_name="Текст письма")
    is_html = models.BooleanField(default=False, verbose_name="HTML-формат")
    
    class Meta:
        verbose_name = "Email"
        verbose_name_plural = "Emails"

class Note(Activity):
    """
    Модель для заметок
    """
    # Дополнительные поля для заметок
    text = models.TextField(verbose_name="Текст заметки")
    
    class Meta:
        verbose_name = "Заметка"
        verbose_name_plural = "Заметки"

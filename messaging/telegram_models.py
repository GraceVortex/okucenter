from django.db import models
from django.utils import timezone
from django.conf import settings
from accounts.models import Student, Parent

class TelegramUser(models.Model):
    """Модель для хранения информации о пользователях Telegram"""
    
    ROLE_CHOICES = (
        ('student', 'Студент'),
        ('parent', 'Родитель'),
        ('teacher', 'Преподаватель'),
        ('admin', 'Администратор'),
        ('reception', 'Ресепшн'),
        ('unknown', 'Неизвестно'),
    )
    
    telegram_id = models.CharField(max_length=20, unique=True, verbose_name="Telegram ID")
    username = models.CharField(max_length=100, blank=True, null=True, verbose_name="Username")
    first_name = models.CharField(max_length=100, blank=True, null=True, verbose_name="Имя")
    last_name = models.CharField(max_length=100, blank=True, null=True, verbose_name="Фамилия")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Телефон")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='unknown', verbose_name="Роль")
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, blank=True, null=True, related_name='telegram_accounts', verbose_name="Студент")
    parent = models.ForeignKey(Parent, on_delete=models.SET_NULL, blank=True, null=True, related_name='telegram_accounts', verbose_name="Родитель")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Пользователь Telegram"
        verbose_name_plural = "Пользователи Telegram"
    
    def __str__(self):
        if self.username:
            return f"@{self.username}"
        return f"{self.first_name} {self.last_name} ({self.telegram_id})"
    
    def get_full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.username:
            return f"@{self.username}"
        return self.telegram_id


class TelegramBroadcast(models.Model):
    """Модель для хранения информации о рассылках в Telegram"""
    
    STATUS_CHOICES = (
        ('draft', 'Черновик'),
        ('scheduled', 'Запланировано'),
        ('in_progress', 'В процессе'),
        ('completed', 'Завершено'),
        ('failed', 'Ошибка'),
    )
    
    RECIPIENT_TYPE_CHOICES = (
        ('students', 'Студенты'),
        ('parents', 'Родители'),
        ('both', 'Родители и студенты'),
        ('teachers', 'Преподаватели'),
        ('all', 'Все'),
    )
    
    title = models.CharField(max_length=255, verbose_name="Название рассылки")
    message = models.TextField(verbose_name="Текст сообщения")
    recipient_type = models.CharField(max_length=20, choices=RECIPIENT_TYPE_CHOICES, default='both', verbose_name="Тип получателей")
    
    # Фильтры для получателей
    target_class = models.ForeignKey('classes.Class', on_delete=models.SET_NULL, blank=True, null=True, related_name='telegram_broadcasts', verbose_name="Класс")
    target_schedule = models.ForeignKey('classes.ClassSchedule', on_delete=models.SET_NULL, blank=True, null=True, related_name='telegram_broadcasts', verbose_name="Расписание")
    target_day = models.IntegerField(blank=True, null=True, verbose_name="День недели")
    
    # Медиа-файлы
    media_file = models.FileField(upload_to='telegram_media/', blank=True, null=True, verbose_name="Медиа-файл")
    media_type = models.CharField(max_length=20, blank=True, null=True, verbose_name="Тип медиа")
    
    # Дополнительные параметры для Telegram
    has_buttons = models.BooleanField(default=False, verbose_name="Есть кнопки")
    buttons_json = models.TextField(blank=True, null=True, verbose_name="JSON кнопок")
    
    # Статус и время
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="Статус")
    scheduled_at = models.DateTimeField(blank=True, null=True, verbose_name="Запланировано на")
    sent_at = models.DateTimeField(blank=True, null=True, verbose_name="Отправлено")
    
    # Статистика
    total_recipients = models.IntegerField(default=0, verbose_name="Всего получателей")
    successful_sent = models.IntegerField(default=0, verbose_name="Успешно отправлено")
    failed_sent = models.IntegerField(default=0, verbose_name="Ошибок при отправке")
    
    # Мета-информация
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='telegram_broadcasts', verbose_name="Создатель")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Telegram рассылка"
        verbose_name_plural = "Telegram рассылки"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def get_recipients(self):
        """Получает список получателей на основе фильтров"""
        from accounts.models import Student, Parent
        
        recipients = []
        
        # Базовый QuerySet для студентов
        students_qs = Student.objects.all()
        
        # Применяем фильтры для студентов
        if self.target_class:
            students_qs = students_qs.filter(class_obj=self.target_class)
        
        if self.target_schedule:
            # Получаем студентов, которые записаны на данное расписание
            students_qs = students_qs.filter(enrollments__class_obj=self.target_schedule.class_obj)
        
        if self.target_day is not None:
            # Если указан день недели, фильтруем по расписаниям в этот день
            if self.target_schedule:
                if self.target_schedule.day_of_week != self.target_day:
                    students_qs = Student.objects.none()
            else:
                # Получаем все расписания для указанного дня
                schedules = self.target_class.schedules.filter(day_of_week=self.target_day) if self.target_class else None
                if schedules:
                    students_qs = students_qs.filter(enrollments__class_obj__schedules__in=schedules).distinct()
        
        # Получаем Telegram аккаунты для студентов
        if self.recipient_type in ['students', 'both', 'all']:
            for student in students_qs:
                telegram_accounts = TelegramUser.objects.filter(student=student, is_active=True)
                for account in telegram_accounts:
                    recipients.append({
                        'id': account.telegram_id,
                        'name': account.get_full_name(),
                        'type': 'student',
                        'student_name': student.get_full_name()
                    })
        
        # Получаем Telegram аккаунты для родителей
        if self.recipient_type in ['parents', 'both', 'all']:
            # Если у нас уже есть фильтрованный список студентов, получаем их родителей
            if self.recipient_type != 'all':
                parents = Parent.objects.filter(children__in=students_qs).distinct()
            else:
                parents = Parent.objects.all()
            
            for parent in parents:
                telegram_accounts = TelegramUser.objects.filter(parent=parent, is_active=True)
                for account in telegram_accounts:
                    # Находим имя первого ребенка для отображения
                    child_name = ""
                    if parent.children.exists():
                        child_name = parent.children.first().get_full_name()
                    
                    recipients.append({
                        'id': account.telegram_id,
                        'name': account.get_full_name(),
                        'type': 'parent',
                        'student_name': child_name
                    })
        
        # Получаем Telegram аккаунты для преподавателей
        if self.recipient_type in ['teachers', 'all']:
            from accounts.models import Teacher
            teachers_qs = Teacher.objects.all()
            
            # Применяем фильтры для преподавателей
            if self.target_class:
                teachers_qs = teachers_qs.filter(classes=self.target_class)
            
            for teacher in teachers_qs:
                telegram_accounts = TelegramUser.objects.filter(role='teacher', is_active=True)
                for account in telegram_accounts:
                    recipients.append({
                        'id': account.telegram_id,
                        'name': account.get_full_name(),
                        'type': 'teacher'
                    })
        
        return recipients


class TelegramMessage(models.Model):
    """Модель для хранения информации об отдельных сообщениях в рассылке"""
    
    STATUS_CHOICES = (
        ('pending', 'Ожидает отправки'),
        ('sent', 'Отправлено'),
        ('delivered', 'Доставлено'),
        ('read', 'Прочитано'),
        ('failed', 'Ошибка'),
    )
    
    broadcast = models.ForeignKey(TelegramBroadcast, on_delete=models.CASCADE, related_name='messages', verbose_name="Рассылка")
    recipient = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name='messages', verbose_name="Получатель")
    
    # Данные о получателе для удобства
    recipient_type = models.CharField(max_length=20, verbose_name="Тип получателя")
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, blank=True, null=True, related_name='telegram_messages', verbose_name="Студент")
    parent = models.ForeignKey(Parent, on_delete=models.SET_NULL, blank=True, null=True, related_name='telegram_messages', verbose_name="Родитель")
    
    # Статус сообщения
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Статус")
    telegram_message_id = models.CharField(max_length=50, blank=True, null=True, verbose_name="ID сообщения в Telegram")
    
    # Время отправки и доставки
    sent_at = models.DateTimeField(blank=True, null=True, verbose_name="Время отправки")
    delivered_at = models.DateTimeField(blank=True, null=True, verbose_name="Время доставки")
    read_at = models.DateTimeField(blank=True, null=True, verbose_name="Время прочтения")
    
    # Ошибки
    error_message = models.TextField(blank=True, null=True, verbose_name="Сообщение об ошибке")
    
    # Мета-информация
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Сообщение Telegram"
        verbose_name_plural = "Сообщения Telegram"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Сообщение для {self.recipient} ({self.get_status_display()})"

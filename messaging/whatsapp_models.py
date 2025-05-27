from django.db import models
from django.utils import timezone
from accounts.models import User, Student, Parent
from classes.models import Class, ClassSchedule

class WhatsAppBroadcast(models.Model):
    """Модель для хранения рассылок WhatsApp"""
    
    # Метаданные рассылки
    title = models.CharField(max_length=255, verbose_name="Название рассылки")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='whatsapp_broadcasts')
    created_at = models.DateTimeField(auto_now_add=True)
    scheduled_at = models.DateTimeField(null=True, blank=True, verbose_name="Запланировано на")
    
    # Содержимое сообщения
    message = models.TextField(verbose_name="Текст сообщения")
    
    # Медиа-файлы (опционально)
    media_file = models.FileField(upload_to='whatsapp_media/', null=True, blank=True, verbose_name="Медиа-файл")
    
    # Фильтры для получателей
    target_class = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Класс")
    target_schedule = models.ForeignKey(ClassSchedule, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Расписание")
    target_day = models.IntegerField(null=True, blank=True, verbose_name="День недели", 
                                    choices=[(0, "Понедельник"), (1, "Вторник"), (2, "Среда"), 
                                            (3, "Четверг"), (4, "Пятница"), (5, "Суббота"), (6, "Воскресенье")])
    
    # Тип получателей
    RECIPIENT_CHOICES = (
        ('parents', 'Родители'),
        ('students', 'Студенты'),
        ('both', 'Родители и студенты'),
    )
    recipient_type = models.CharField(max_length=10, choices=RECIPIENT_CHOICES, default='parents', verbose_name="Тип получателей")
    
    # Статус рассылки
    STATUS_CHOICES = (
        ('draft', 'Черновик'),
        ('scheduled', 'Запланировано'),
        ('in_progress', 'В процессе'),
        ('completed', 'Завершено'),
        ('failed', 'Ошибка'),
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='draft', verbose_name="Статус")
    
    # Статистика
    total_recipients = models.IntegerField(default=0, verbose_name="Всего получателей")
    successful_sent = models.IntegerField(default=0, verbose_name="Успешно отправлено")
    failed_sent = models.IntegerField(default=0, verbose_name="Ошибок отправки")
    
    class Meta:
        verbose_name = 'Рассылка WhatsApp'
        verbose_name_plural = 'Рассылки WhatsApp'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Рассылка: {self.title} ({self.get_status_display()})"
    
    def get_recipients(self):
        """Возвращает список получателей рассылки на основе фильтров"""
        # Базовый запрос для студентов
        students_query = Student.objects.filter(is_active=True)
        
        # Применяем фильтры, если они указаны
        if self.target_class:
            # Получаем студентов, записанных на этот класс
            students_query = students_query.filter(enrollments__class_obj=self.target_class, 
                                                 enrollments__is_active=True)
        
        if self.target_schedule:
            # Получаем студентов, записанных на занятия по этому расписанию
            class_obj = self.target_schedule.class_obj
            students_query = students_query.filter(enrollments__class_obj=class_obj, 
                                                 enrollments__is_active=True)
        
        if self.target_day is not None:
            # Если указан день недели, фильтруем студентов, у которых есть занятия в этот день
            if self.target_schedule:
                # Если указано конкретное расписание, проверяем его день недели
                if self.target_schedule.day_of_week != self.target_day:
                    # День недели расписания не совпадает с указанным днем
                    return []
            else:
                # Получаем все расписания на указанный день
                schedules = ClassSchedule.objects.filter(day_of_week=self.target_day)
                if self.target_class:
                    # Если указан класс, фильтруем расписания только для этого класса
                    schedules = schedules.filter(class_obj=self.target_class)
                
                # Получаем студентов, записанных на занятия по этим расписаниям
                class_ids = schedules.values_list('class_obj_id', flat=True)
                students_query = students_query.filter(enrollments__class_obj_id__in=class_ids, 
                                                     enrollments__is_active=True)
        
        # Получаем уникальных студентов
        students = students_query.distinct()
        
        # Формируем список получателей в зависимости от типа
        recipients = []
        if self.recipient_type in ['students', 'both']:
            # Добавляем студентов с номерами телефонов
            for student in students:
                if student.phone_number:
                    recipients.append({
                        'type': 'student',
                        'id': student.id,
                        'name': student.full_name,
                        'phone': student.phone_number
                    })
        
        if self.recipient_type in ['parents', 'both']:
            # Добавляем родителей студентов с номерами телефонов
            for student in students:
                if student.parent and student.parent.phone_number:
                    recipients.append({
                        'type': 'parent',
                        'id': student.parent.id,
                        'name': student.parent.full_name,
                        'phone': student.parent.phone_number,
                        'student_name': student.full_name
                    })
        
        return recipients


class WhatsAppMessage(models.Model):
    """Модель для хранения отдельных сообщений WhatsApp в рамках рассылки"""
    
    # Связь с рассылкой
    broadcast = models.ForeignKey(WhatsAppBroadcast, on_delete=models.CASCADE, related_name='messages')
    
    # Получатель
    recipient_type = models.CharField(max_length=10, choices=(('parent', 'Родитель'), ('student', 'Студент')))
    recipient_id = models.IntegerField()  # ID родителя или студента
    recipient_name = models.CharField(max_length=255)
    recipient_phone = models.CharField(max_length=20)
    
    # Статус сообщения
    STATUS_CHOICES = (
        ('pending', 'Ожидает отправки'),
        ('sent', 'Отправлено'),
        ('delivered', 'Доставлено'),
        ('read', 'Прочитано'),
        ('failed', 'Ошибка'),
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    
    # Метаданные сообщения
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Информация об ошибке (если есть)
    error_message = models.TextField(null=True, blank=True)
    
    # Идентификатор сообщения в WhatsApp
    whatsapp_message_id = models.CharField(max_length=255, null=True, blank=True)
    
    class Meta:
        verbose_name = 'Сообщение WhatsApp'
        verbose_name_plural = 'Сообщения WhatsApp'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Сообщение для {self.recipient_name} ({self.get_status_display()})"

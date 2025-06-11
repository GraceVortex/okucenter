from django.db import models
from django.core.exceptions import ValidationError
from accounts.models import Student, Teacher
from classes.models import Class
from django.utils import timezone

class NonScheduledLesson(models.Model):
    """
    Модель для уроков не по расписанию (одноразовых).
    Хранит информацию о внеплановых уроках, включая учеников, преподавателя,
    стоимость и статус оплаты.
    """
    LESSON_TYPE_CHOICES = (
        ('trial', 'Пробный'),
        ('regular', 'Обычный'),
    )
    
    TRIAL_STATUS_CHOICES = (
        ('pending', 'Ожидает решения'),
        ('continued', 'Продолжил обучение'),
        ('discontinued', 'Не продолжил обучение'),
    )
    
    name = models.CharField(max_length=100, verbose_name="Название урока", db_index=True)
    teacher = models.ForeignKey(
        Teacher, 
        on_delete=models.CASCADE, 
        related_name='non_scheduled_lessons',
        verbose_name="Преподаватель",
        db_index=True
    )
    students = models.ManyToManyField(
        Student,
        related_name='non_scheduled_lessons',
        verbose_name="Ученики"
    )
    date = models.DateField(verbose_name="Дата урока", db_index=True)
    time = models.TimeField(verbose_name="Время урока")
    duration = models.IntegerField(default=60, verbose_name="Продолжительность (минуты)")
    
    lesson_type = models.CharField(
        max_length=10,
        choices=LESSON_TYPE_CHOICES,
        default='regular',
        verbose_name="Тип урока",
        db_index=True
    )
    
    trial_status = models.CharField(
        max_length=15,
        choices=TRIAL_STATUS_CHOICES,
        default='pending',
        verbose_name="Статус пробного урока",
        db_index=True,
        null=True,
        blank=True
    )
    
    price_per_student = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Стоимость для ученика"
    )
    
    teacher_payment = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Оплата преподавателю"
    )
    
    is_completed = models.BooleanField(default=False, verbose_name="Урок проведен")
    is_paid_to_teacher = models.BooleanField(default=False, verbose_name="Оплачено преподавателю")
    
    notes = models.TextField(blank=True, null=True, verbose_name="Примечания")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания", db_index=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Урок не по расписанию"
        verbose_name_plural = "Уроки не по расписанию"
        ordering = ['-date', '-time']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['teacher']),
            models.Index(fields=['date']),
            models.Index(fields=['lesson_type']),
            models.Index(fields=['trial_status']),
        ]
    
    def clean(self):
        """Валидация на уровне модели"""
        if self.price_per_student < 0:
            raise ValidationError({
                'price_per_student': "Стоимость для ученика не может быть отрицательной."
            })
        
        if self.teacher_payment < 0:
            raise ValidationError({
                'teacher_payment': "Оплата преподавателю не может быть отрицательной."
            })
        
        if self.lesson_type == 'regular' and self.trial_status:
            self.trial_status = None
            
        if self.lesson_type == 'trial' and not self.trial_status:
            self.trial_status = 'pending'
    
    def __str__(self):
        return f"{self.name} ({self.date.strftime('%d.%m.%Y')})"
    
    def is_in_future(self):
        """Проверяет, запланирован ли урок на будущее"""
        now = timezone.now()
        lesson_datetime = timezone.make_aware(
            timezone.datetime.combine(self.date, self.time)
        )
        return lesson_datetime > now
    
    def charge_students(self):
        """Снимает оплату с баланса учеников"""
        # Только для обычных уроков или пробных с продолжением обучения
        if self.lesson_type == 'regular' or (self.lesson_type == 'trial' and self.trial_status == 'continued'):
            for student in self.students.all():
                student.balance -= self.price_per_student
                student.save()
                
    def mark_as_completed(self):
        """Отмечает урок как проведенный"""
        self.is_completed = True
        self.save()


class NonScheduledLessonAttendance(models.Model):
    """
    Модель для отметки посещаемости на уроках не по расписанию.
    """
    lesson = models.ForeignKey(
        NonScheduledLesson,
        on_delete=models.CASCADE,
        related_name='attendances',
        verbose_name="Урок"
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='non_scheduled_attendances',
        verbose_name="Ученик"
    )
    is_present = models.BooleanField(default=False, verbose_name="Присутствовал")
    marked_by = models.CharField(max_length=100, blank=True, null=True, verbose_name="Кто отметил")
    marked_at = models.DateTimeField(auto_now_add=True, verbose_name="Когда отмечено")
    
    class Meta:
        verbose_name = "Посещаемость внепланового урока"
        verbose_name_plural = "Посещаемость внеплановых уроков"
        unique_together = ['lesson', 'student']
        
    def __str__(self):
        status = "Присутствовал" if self.is_present else "Отсутствовал"
        return f"{self.student.full_name} - {self.lesson.name} - {status}"

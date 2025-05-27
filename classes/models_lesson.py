from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from accounts.models import Student, Teacher
from .models import Class, ClassSchedule

class LessonMaterial(models.Model):
    """
    Модель материалов урока.
    Хранит информацию о материалах, прикрепленных к определенному занятию.
    """
    class_obj = models.ForeignKey(
        Class, 
        on_delete=models.CASCADE, 
        related_name='lesson_materials',
        verbose_name="Класс",
        db_index=True
    )
    schedule = models.ForeignKey(
        ClassSchedule,
        on_delete=models.CASCADE,
        related_name='lesson_materials',
        verbose_name="Расписание",
        db_index=True
    )
    title = models.CharField(max_length=255, verbose_name="Название")
    description = models.TextField(verbose_name="Описание", blank=True, default="")
    file = models.FileField(
        upload_to='lesson_materials/', 
        blank=True, 
        null=True,
        verbose_name="Файл"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    
    class Meta:
        verbose_name = "Материал урока"
        verbose_name_plural = "Материалы уроков"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['class_obj', 'schedule']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.class_obj.name} ({self.schedule.get_day_of_week_display()})"


class StudentLessonGrade(models.Model):
    """
    Модель оценок студентов за уроки.
    Хранит информацию об оценках студентов за конкретные занятия.
    """
    student = models.ForeignKey(
        Student, 
        on_delete=models.CASCADE, 
        related_name='lesson_grades',
        verbose_name="Студент",
        db_index=True
    )
    schedule = models.ForeignKey(
        ClassSchedule,
        on_delete=models.CASCADE,
        related_name='student_grades',
        verbose_name="Расписание",
        db_index=True
    )
    grade = models.PositiveSmallIntegerField(
        verbose_name="Оценка",
        help_text="Оценка за урок (от 0 до 100)"
    )
    comment = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Комментарий преподавателя"
    )
    date = models.DateField(
        default=timezone.now,
        verbose_name="Дата урока",
        db_index=True
    )
    
    class Meta:
        verbose_name = "Оценка за урок"
        verbose_name_plural = "Оценки за уроки"
        ordering = ['-date']
        unique_together = ('student', 'schedule', 'date')
        indexes = [
            models.Index(fields=['student', 'schedule']),
            models.Index(fields=['student', '-date']),
        ]
    
    def clean(self):
        """Валидация на уровне модели"""
        if self.grade < 0 or self.grade > 100:
            raise ValidationError({
                'grade': "Оценка должна быть в диапазоне от 0 до 100."
            })
    
    def __str__(self):
        return f"Оценка {self.student.full_name} за урок {self.schedule} ({self.date})"

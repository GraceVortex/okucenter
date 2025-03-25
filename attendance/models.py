from django.db import models

# Create your models here.
from django.db import models
from accounts.models import Student, Teacher, User
from classes.models import Class, ClassSchedule

class Attendance(models.Model):
    STATUS_CHOICES = (
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('excused', 'Excused'),
        ('canceled', 'Canceled'),  
    )
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='attendances')
    class_schedule = models.ForeignKey(ClassSchedule, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='absent')
    teacher_confirmed = models.BooleanField(default=False)
    reception_confirmed = models.BooleanField(default=False)
    is_canceled = models.BooleanField(default=False, help_text="Флаг, указывающий, что урок отменен")
    substitute_teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name='substituted_attendances', help_text="Заменяющий учитель")
    
    class Meta:
        unique_together = ('student', 'class_obj', 'date')
    
    def __str__(self):
        return f"{self.student.full_name} - {self.class_obj.name} - {self.date}"

class CanceledAttendance(models.Model):
    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, related_name='cancellations')
    canceled_by = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='canceled_attendances')
    canceled_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(max_length=500, help_text="Причина отмены посещения (макс. 50 слов)")
    
    def __str__(self):
        return f"Отмена: {self.attendance} - {self.canceled_at.strftime('%d.%m.%Y %H:%M')}"

class CancellationRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Ожидает подтверждения'),
        ('approved', 'Подтверждено'),
        ('rejected', 'Отклонено'),
    )
    
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='cancellation_requests')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='cancellation_requests')
    class_schedule = models.ForeignKey(ClassSchedule, on_delete=models.CASCADE, related_name='cancellation_requests')
    date = models.DateField(help_text="Дата урока, который нужно отменить")
    reason = models.TextField(max_length=500, help_text="Причина отмены урока")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    needs_substitute = models.BooleanField(default=False, help_text="Требуется ли заменяющий учитель")
    substitute_teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name='substitute_requests')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_cancellations')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Запрос на отмену урока"
        verbose_name_plural = "Запросы на отмену уроков"
    
    def __str__(self):
        return f"Запрос на отмену: {self.class_obj.name} - {self.date}"

class Mark(models.Model):
    HOMEWORK_CHOICES = (
        ('completed', 'Completed'),
        ('partial', 'Partially Completed'),
        ('not_completed', 'Not Completed'),
    )
    
    ACTIVITY_CHOICES = (
        ('excellent', 'Excellent'),
        ('normal', 'Normal'),
        ('poor', 'Poor'),
    )
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='marks')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='marks')
    date = models.DateField()
    homework_mark = models.CharField(max_length=15, choices=HOMEWORK_CHOICES, blank=True, null=True)
    activity_mark = models.CharField(max_length=10, choices=ACTIVITY_CHOICES, blank=True, null=True)
    teacher_comment = models.CharField(max_length=150, blank=True, null=True)
    substitute_teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name='substitute_marks')
    
    class Meta:
        unique_together = ('student', 'class_obj', 'date')
    
    def __str__(self):
        return f"Mark for {self.student.full_name} in {self.class_obj.name} on {self.date}"
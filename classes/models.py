from django.db import models

# Create your models here.
from django.db import models
from accounts.models import Teacher, Student

class Class(models.Model):
    PAYMENT_TYPE_CHOICES = (
        ('percentage', 'Процент от стоимости урока'),
        ('fixed', 'Фиксированная оплата'),
    )
    
    name = models.CharField(max_length=100)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='classes')
    price_per_lesson = models.DecimalField(max_digits=10, decimal_places=2)
    teacher_payment_type = models.CharField(max_length=10, choices=PAYMENT_TYPE_CHOICES, default='percentage', help_text="Тип оплаты преподавателя")
    teacher_percentage = models.IntegerField(default=0, help_text="Процент от стоимости занятия, который получает преподаватель")
    teacher_fixed_payment = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Фиксированная оплата преподавателя за занятие")
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class ClassSchedule(models.Model):
    DAY_CHOICES = (
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    )
    
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='schedules')
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.IntegerField(choices=[(i, f'Room {i}') for i in range(1, 9)])
    
    def __str__(self):
        return f"{self.class_obj.name} - {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"

class Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='enrollments')
    enrollment_date = models.DateField(auto_now_add=True)
    
    class Meta:
        unique_together = ('student', 'class_obj')
    
    def __str__(self):
        return f"{self.student.full_name} - {self.class_obj.name}"

class ClassworkFile(models.Model):
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='classwork_files')
    date = models.DateField()
    file = models.FileField(upload_to='classwork_files/')
    description = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"Classwork for {self.class_obj.name} on {self.date}"

class Homework(models.Model):
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='homework')
    date = models.DateField()
    description = models.TextField()
    file = models.FileField(upload_to='homework_files/', blank=True, null=True)
    
    def __str__(self):
        return f"Homework for {self.class_obj.name} on {self.date}"

class HomeworkSubmission(models.Model):
    COMPLETION_CHOICES = (
        ('completed', 'Выполнено'),
        ('partially_completed', 'Частично выполнено'),
        ('not_completed', 'Не выполнено'),
    )
    
    homework = models.ForeignKey(Homework, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='homework_submissions')
    file = models.FileField(upload_to='homework_submissions/')
    submission_date = models.DateTimeField(auto_now_add=True)
    completion_status = models.CharField(max_length=20, choices=COMPLETION_CHOICES, blank=True, null=True)
    teacher_comment = models.CharField(max_length=150, blank=True, null=True)
    
    def __str__(self):
        return f"Submission by {self.student.full_name} for {self.homework}"
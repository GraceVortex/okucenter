from django.db import models
from django.utils import timezone
import os
import base64
from io import BytesIO
from PIL import Image

# Create your models here.
from accounts.models import Student, Teacher, User
from classes.models import Class, ClassSchedule

class Attendance(models.Model):
    STATUS_CHOICES = (
        ('present', 'Присутствует'),
        ('absent', 'Отсутствует'),
        ('excused', 'Уважительная причина'),
        ('canceled', 'Отменено'),  
    )
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='attendances')
    class_schedule = models.ForeignKey(ClassSchedule, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='absent')
    teacher_confirmed = models.BooleanField(default=False)
    reception_confirmed = models.BooleanField(default=False)
    reception_confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='confirmed_attendances')
    is_canceled = models.BooleanField(default=False, help_text="Флаг, указывающий, что урок отменен")
    substitute_teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name='substituted_attendances', help_text="Заменяющий учитель")
    face_id_confirmed = models.BooleanField(default=False, help_text="Флаг, указывающий, что посещаемость подтверждена через Face ID")
    
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
        verbose_name = "Запрос на отмену урока от учителя"
        verbose_name_plural = "Запросы на отмену уроков от учителей"
    
    def __str__(self):
        return f"Запрос на отмену от учителя: {self.class_obj.name} - {self.date}"


class StudentCancellationRequest(models.Model):
    """
    Модель для запросов на отмену занятий от учеников или их родителей.
    Если запрос создан за 24 часа до занятия, то он может быть одобрен и деньги не будут сняты.
    В противном случае, запрос будет отклонен автоматически.
    """
    STATUS_CHOICES = (
        ('pending', 'Ожидает подтверждения'),
        ('approved', 'Подтверждено'),
        ('rejected', 'Отклонено'),
    )
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='cancellation_requests')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='student_cancellation_requests')
    class_schedule = models.ForeignKey(ClassSchedule, on_delete=models.CASCADE, related_name='student_cancellation_requests')
    date = models.DateField(help_text="Дата урока, который нужно отменить")
    reason = models.TextField(max_length=500, help_text="Причина отмены урока")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_student_cancellations', help_text="Пользователь, создавший запрос (студент или родитель)")
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_student_cancellations', help_text="Пользователь, обработавший запрос (администратор или ресепшн)")
    attendance = models.ForeignKey('Attendance', on_delete=models.SET_NULL, null=True, blank=True, related_name='cancellation_request', help_text="Связанная запись о посещаемости")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Запрос на отмену урока от ученика"
        verbose_name_plural = "Запросы на отмену уроков от учеников"
        unique_together = ('student', 'class_obj', 'date')  # Один ученик может создать только один запрос на отмену для конкретного урока
    
    def __str__(self):
        return f"Запрос на отмену от ученика: {self.student.full_name} - {self.class_obj.name} - {self.date}"
    
    def is_within_24_hours(self):
        """
        Проверяет, создан ли запрос менее чем за 24 часа до занятия.
        """
        from django.utils import timezone
        import datetime
        
        # Получаем время начала занятия из расписания
        lesson_datetime = datetime.datetime.combine(
            self.date,
            self.class_schedule.start_time,
            tzinfo=timezone.get_current_timezone()
        )
        
        # Текущее время с учетом часового пояса
        now = timezone.now()
        
        # Разница во времени в часах
        time_difference = (lesson_datetime - now).total_seconds() / 3600
        
        return time_difference < 24

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

class FaceAttendance(models.Model):
    """
    Модель для хранения данных о посещаемости с распознаванием лиц.
    Связывает запись о посещаемости с данными о распознавании лица.
    """
    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, related_name='face_attendances')
    confidence = models.FloatField(default=0.0, help_text="Уровень уверенности при распознавании лица")
    created_at = models.DateTimeField(default=timezone.now)
    face_image = models.ImageField(upload_to='face_attendance/', blank=True, null=True, help_text="Изображение лица, использованное для распознавания")
    reception_confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='confirmed_face_attendances')
    
    class Meta:
        verbose_name = "Посещаемость по лицу"
        verbose_name_plural = "Посещаемость по лицу"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Face Attendance: {self.attendance} - {self.created_at.strftime('%d.%m.%Y %H:%M')}"
    
    def save_image(self, image_data):
        """
        Сохраняет изображение лица из байтов или base64-строки
        """
        try:
            # Если это строка base64, декодируем её
            if isinstance(image_data, str):
                if ',' in image_data:
                    image_data = image_data.split(',')[1]
                image_data = base64.b64decode(image_data)
            
            # Открываем изображение
            image = Image.open(BytesIO(image_data))
            
            # Создаем имя файла
            filename = f"face_{self.attendance.student.id}_{timezone.now().strftime('%Y%m%d%H%M%S')}.jpg"
            
            # Сохраняем изображение во временный буфер
            buffer = BytesIO()
            image.save(buffer, format='JPEG')
            
            # Сохраняем в поле модели
            self.face_image.save(filename, buffer, save=False)
            self.save()
            
            return True
        except Exception as e:
            print(f"Ошибка при сохранении изображения: {e}")
            return False
from django.db import models
from accounts.models import User, Student
from attendance.models import Attendance

# Create your models here.

class FaceRecognitionLog(models.Model):
    """Модель для хранения логов распознавания лиц"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='face_recognition_logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=False, db_index=True)
    confidence = models.FloatField(default=0.0, help_text="Уровень уверенности распознавания (0-1)")
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    device_info = models.CharField(max_length=255, blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.timestamp} - {'Успешно' if self.success else 'Неудачно'}"
    
    class Meta:
        verbose_name = "Лог распознавания лица"
        verbose_name_plural = "Логи распознавания лиц"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['success']),
            models.Index(fields=['user', '-timestamp']),
        ]

class FaceAttendance(models.Model):
    """Модель для хранения отметок посещаемости через распознавание лиц"""
    attendance = models.OneToOneField(Attendance, on_delete=models.CASCADE, related_name='face_attendance')
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    confidence = models.FloatField(default=0.0, help_text="Уровень уверенности распознавания (0-1)")
    image = models.ImageField(upload_to='face_attendance/', blank=True, null=True)
    
    @property
    def student(self):
        """Свойство для прямого доступа к студенту из связанной записи посещаемости"""
        return self.attendance.student if self.attendance else None
    
    def save_image(self, image_data):
        """Метод для сохранения изображения из байтов"""
        from django.core.files.base import ContentFile
        import uuid
        
        if not self.image:
            filename = f"face_attendance_{uuid.uuid4()}.jpg"
            self.image.save(filename, ContentFile(image_data), save=True)
    
    def __str__(self):
        if self.attendance and hasattr(self.attendance, 'student') and self.attendance.student:
            return f"{self.attendance.student.full_name} - {self.attendance.date} - {self.timestamp}"
        return f"Посещение {self.attendance.date if self.attendance else 'неизвестно'} - {self.timestamp}"
    
    class Meta:
        verbose_name = "Отметка посещаемости по лицу"
        verbose_name_plural = "Отметки посещаемости по лицу"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
        ]

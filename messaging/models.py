from django.db import models
from django.utils import timezone
from accounts.models import User

# Create your models here.

class Conversation(models.Model):
    """Модель для хранения диалогов между пользователями"""
    
    # Участники диалога
    participants = models.ManyToManyField(User, related_name='conversations')
    
    # Метаданные диалога
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Тема диалога
    subject = models.CharField(max_length=255, blank=True, null=True)
    
    # Статус диалога
    STATUS_CHOICES = (
        ('active', 'Активный'),
        ('closed', 'Закрытый'),
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    
    class Meta:
        verbose_name = 'Диалог'
        verbose_name_plural = 'Диалоги'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Диалог {self.id}: {self.subject or 'Без темы'}"
    
    def get_last_message(self):
        """Возвращает последнее сообщение в диалоге"""
        return self.messages.order_by('-created_at').first()
    
    def mark_as_read(self, user):
        """Отмечает все сообщения в диалоге как прочитанные для указанного пользователя"""
        self.messages.filter(is_read=False).exclude(sender=user).update(is_read=True)


class Message(models.Model):
    """Модель для хранения сообщений"""
    
    # Связь с диалогом
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    
    # Отправитель сообщения
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    
    # Содержимое сообщения
    content = models.TextField()
    
    # Метаданные сообщения
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        ordering = ['created_at']
    
    def __str__(self):
        return f"Сообщение от {self.sender} ({self.created_at.strftime('%d.%m.%Y %H:%M')})"
    
    def mark_as_read(self):
        """Отмечает сообщение как прочитанное"""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])

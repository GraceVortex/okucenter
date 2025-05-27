import logging
import uuid
import json
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from accounts.models import User
from .models_new import Contact, Company, Deal

logger = logging.getLogger(__name__)

class Integration(models.Model):
    """
    Базовая модель для интеграций с внешними сервисами
    """
    INTEGRATION_TYPE_CHOICES = (
        ('whatsapp', 'WhatsApp'),
        ('instagram', 'Instagram'),
        ('telegram', 'Telegram'),
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('custom', 'Пользовательская'),
    )
    
    name = models.CharField(max_length=100, verbose_name="Название интеграции")
    integration_type = models.CharField(max_length=20, choices=INTEGRATION_TYPE_CHOICES, verbose_name="Тип интеграции")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    
    # Настройки интеграции в формате JSON
    settings = models.JSONField(default=dict, verbose_name="Настройки интеграции")
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                  related_name="created_integrations", verbose_name="Создал")
    
    class Meta:
        verbose_name = "Интеграция"
        verbose_name_plural = "Интеграции"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_integration_type_display()})"

class SocialAccount(models.Model):
    """
    Модель для хранения информации о социальных аккаунтах
    """
    ACCOUNT_TYPE_CHOICES = (
        ('whatsapp', 'WhatsApp'),
        ('instagram', 'Instagram'),
        ('telegram', 'Telegram'),
        ('facebook', 'Facebook'),
        ('vk', 'ВКонтакте'),
        ('other', 'Другое'),
    )
    
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="social_accounts", 
                               verbose_name="Контакт")
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, verbose_name="Тип аккаунта")
    username = models.CharField(max_length=100, verbose_name="Имя пользователя")
    account_id = models.CharField(max_length=100, blank=True, null=True, verbose_name="ID аккаунта")
    url = models.URLField(blank=True, null=True, verbose_name="URL профиля")
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Социальный аккаунт"
        verbose_name_plural = "Социальные аккаунты"
        ordering = ['contact', 'account_type']
        unique_together = ['contact', 'account_type', 'username']
    
    def __str__(self):
        return f"{self.contact} - {self.get_account_type_display()}: {self.username}"

class Message(models.Model):
    """
    Модель для хранения сообщений из различных каналов связи
    """
    MESSAGE_TYPE_CHOICES = (
        ('incoming', 'Входящее'),
        ('outgoing', 'Исходящее'),
    )
    
    CHANNEL_CHOICES = (
        ('whatsapp', 'WhatsApp'),
        ('instagram', 'Instagram'),
        ('telegram', 'Telegram'),
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('other', 'Другое'),
    )
    
    # Уникальный идентификатор сообщения
    message_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="ID сообщения")
    
    # Тип и канал сообщения
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, verbose_name="Тип сообщения")
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, verbose_name="Канал связи")
    
    # Содержимое сообщения
    text = models.TextField(blank=True, null=True, verbose_name="Текст сообщения")
    media_url = models.URLField(blank=True, null=True, verbose_name="URL медиа")
    media_type = models.CharField(max_length=50, blank=True, null=True, verbose_name="Тип медиа")
    
    # Связь с контактом
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="messages", 
                               verbose_name="Контакт")
    
    # Связь с интеграцией
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE, related_name="messages", 
                                   verbose_name="Интеграция")
    
    # Метаданные сообщения
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Метаданные")
    
    # Статус сообщения
    is_read = models.BooleanField(default=False, verbose_name="Прочитано")
    is_delivered = models.BooleanField(default=False, verbose_name="Доставлено")
    
    # Даты
    sent_at = models.DateTimeField(verbose_name="Дата отправки")
    delivered_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата доставки")
    read_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата прочтения")
    
    # Метаданные записи
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания записи")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления записи")
    
    class Meta:
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"
        ordering = ['-sent_at']
    
    def __str__(self):
        return f"{self.get_channel_display()} {self.get_message_type_display()} от {self.contact} ({self.sent_at})"

class Conversation(models.Model):
    """
    Модель для группировки сообщений в беседы
    """
    # Уникальный идентификатор беседы
    conversation_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="ID беседы")
    
    # Канал беседы
    channel = models.CharField(max_length=20, choices=Message.CHANNEL_CHOICES, verbose_name="Канал связи")
    
    # Связь с контактом
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="conversations", 
                               verbose_name="Контакт")
    
    # Связь с сотрудником
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name="assigned_conversations", verbose_name="Ответственный")
    
    # Статус беседы
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    is_archived = models.BooleanField(default=False, verbose_name="В архиве")
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    last_message_at = models.DateTimeField(verbose_name="Дата последнего сообщения")
    
    class Meta:
        verbose_name = "Беседа"
        verbose_name_plural = "Беседы"
        ordering = ['-last_message_at']
    
    def __str__(self):
        return f"Беседа с {self.contact} ({self.get_channel_display()})"
    
    def get_messages(self):
        """
        Возвращает все сообщения беседы, отсортированные по дате отправки
        """
        return Message.objects.filter(
            contact=self.contact,
            channel=self.channel
        ).order_by('sent_at')
    
    def get_unread_messages_count(self):
        """
        Возвращает количество непрочитанных сообщений в беседе
        """
        return Message.objects.filter(
            contact=self.contact,
            channel=self.channel,
            message_type='incoming',
            is_read=False
        ).count()

class Webhook(models.Model):
    """
    Модель для хранения вебхуков для интеграций
    """
    name = models.CharField(max_length=100, verbose_name="Название")
    url = models.URLField(verbose_name="URL вебхука")
    secret_key = models.CharField(max_length=100, blank=True, null=True, verbose_name="Секретный ключ")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    
    # События, на которые реагирует вебхук (в формате JSON)
    events = models.JSONField(default=list, verbose_name="События")
    
    # Связь с интеграцией
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE, related_name="webhooks", 
                                   verbose_name="Интеграция")
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                  related_name="created_webhooks", verbose_name="Создал")
    
    class Meta:
        verbose_name = "Вебхук"
        verbose_name_plural = "Вебхуки"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.integration})"

class WebhookLog(models.Model):
    """
    Модель для логирования запросов к вебхукам
    """
    STATUS_CHOICES = (
        ('success', 'Успешно'),
        ('error', 'Ошибка'),
    )
    
    webhook = models.ForeignKey(Webhook, on_delete=models.CASCADE, related_name="logs", 
                               verbose_name="Вебхук")
    event = models.CharField(max_length=50, verbose_name="Событие")
    payload = models.JSONField(verbose_name="Данные запроса")
    response = models.TextField(blank=True, null=True, verbose_name="Ответ")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name="Статус")
    status_code = models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Код ответа")
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    
    class Meta:
        verbose_name = "Лог вебхука"
        verbose_name_plural = "Логи вебхуков"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.webhook} - {self.event} ({self.status})"

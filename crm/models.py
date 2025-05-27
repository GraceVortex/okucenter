import os
import logging
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from accounts.models import User, Marketer

logger = logging.getLogger(__name__)

# Модели для воронки продаж
class SaleStage(models.Model):
    """
    Модель для определения этапов воронки продаж
    """
    name = models.CharField(max_length=100, verbose_name="Название этапа")
    order = models.PositiveSmallIntegerField(verbose_name="Порядок отображения")
    description = models.TextField(blank=True, null=True, verbose_name="Описание этапа")
    conversion_goal = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, 
                                        verbose_name="Целевая конверсия (%)")
    color = models.CharField(max_length=20, default="#3498db", verbose_name="Цвет этапа")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    
    class Meta:
        verbose_name = "Этап воронки продаж"
        verbose_name_plural = "Этапы воронки продаж"
        ordering = ['order']
    
    def __str__(self):
        return self.name

# Модели для лидов
class LeadSource(models.Model):
    """
    Модель для отслеживания источников лидов
    """
    name = models.CharField(max_length=100, verbose_name="Название источника")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    
    class Meta:
        verbose_name = "Источник лида"
        verbose_name_plural = "Источники лидов"
        ordering = ['name']
    
    def __str__(self):
        return self.name

class Lead(models.Model):
    """
    Модель для хранения информации о потенциальных клиентах (лидах)
    """
    LEAD_STATUS_CHOICES = (
        ('new', 'Новый'),
        ('in_progress', 'В работе'),
        ('qualified', 'Квалифицирован'),
        ('converted', 'Конвертирован в студента'),
        ('closed', 'Закрыт (отказ)'),
    )
    
    full_name = models.CharField(max_length=100, verbose_name="ФИО")
    phone_number = models.CharField(max_length=20, verbose_name="Номер телефона")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    source = models.ForeignKey(LeadSource, on_delete=models.SET_NULL, null=True, related_name="leads", verbose_name="Источник")
    current_stage = models.ForeignKey(SaleStage, on_delete=models.SET_NULL, null=True, related_name="current_leads", verbose_name="Текущий этап")
    status = models.CharField(max_length=20, choices=LEAD_STATUS_CHOICES, default='new', verbose_name="Статус")
    notes = models.TextField(blank=True, null=True, verbose_name="Примечания")
    
    # Информация о школьнике
    birth_date = models.DateField(blank=True, null=True, verbose_name="Дата рождения")
    school = models.CharField(max_length=100, blank=True, null=True, verbose_name="Школа")
    current_grade = models.IntegerField(blank=True, null=True, verbose_name="Текущий класс")
    
    # Информация о родителе
    parent_name = models.CharField(max_length=100, blank=True, null=True, verbose_name="ФИО родителя")
    parent_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Телефон родителя")
    
    # Интересы
    interested_subjects = models.TextField(blank=True, null=True, verbose_name="Интересующие предметы")
    
    # Маркетинговая информация
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name="assigned_leads", verbose_name="Ответственный маркетолог")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    converted_to_student = models.ForeignKey('accounts.Student', on_delete=models.SET_NULL, 
                                           null=True, blank=True, related_name="converted_from_lead",
                                           verbose_name="Конвертирован в студента")
    
    # Метаданные
    meta_data = models.JSONField(blank=True, null=True, verbose_name="Метаданные")
    
    class Meta:
        verbose_name = "Лид"
        verbose_name_plural = "Лиды"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['full_name']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.full_name} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        # Если это новый лид и текущий этап не установлен, установим первый этап
        if not self.pk and not self.current_stage:
            first_stage = SaleStage.objects.filter(is_active=True).order_by('order').first()
            if first_stage:
                self.current_stage = first_stage
        
        super().save(*args, **kwargs)
        
        # Если это новый лид, создаем запись в истории статусов
        if self._state.adding and self.current_stage:
            LeadStatusHistory.objects.create(
                lead=self,
                stage=self.current_stage,
                notes=f"Лид создан и добавлен на этап '{self.current_stage.name}'",
                changed_by=self.assigned_to
            )

class LeadStatusHistory(models.Model):
    """
    Модель для отслеживания истории изменений статуса лида в воронке продаж
    """
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="status_history", verbose_name="Лид")
    stage = models.ForeignKey(SaleStage, on_delete=models.CASCADE, related_name="lead_history", verbose_name="Этап")
    entered_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата перехода на этап")
    exited_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата выхода из этапа")
    notes = models.TextField(blank=True, null=True, verbose_name="Примечания")
    
    # Маркетолог, который перевел лида на этот этап
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, 
                                 null=True, blank=True, related_name="lead_status_changes",
                                 verbose_name="Кем изменен")
    
    class Meta:
        verbose_name = "История статуса лида"
        verbose_name_plural = "История статусов лидов"
        ordering = ['-entered_at']
    
    def __str__(self):
        return f"{self.lead.full_name} - {self.stage.name} ({self.entered_at.strftime('%d.%m.%Y %H:%M')})"
    
    @property
    def duration(self):
        """
        Возвращает продолжительность нахождения на этапе
        """
        if not self.exited_at:
            return timezone.now() - self.entered_at
        return self.exited_at - self.entered_at

class Interaction(models.Model):
    """
    Модель для отслеживания взаимодействий с лидами
    """
    INTERACTION_TYPE_CHOICES = (
        ('call', 'Звонок'),
        ('email', 'Email'),
        ('meeting', 'Встреча'),
        ('whatsapp', 'WhatsApp'),
        ('instagram', 'Instagram'),
        ('other', 'Другое'),
    )
    
    INTERACTION_RESULT_CHOICES = (
        ('positive', 'Положительный'),
        ('neutral', 'Нейтральный'),
        ('negative', 'Отрицательный'),
        ('no_answer', 'Нет ответа'),
    )
    
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="interactions", verbose_name="Лид")
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_TYPE_CHOICES, verbose_name="Тип взаимодействия")
    date_time = models.DateTimeField(verbose_name="Дата и время")
    duration = models.PositiveIntegerField(blank=True, null=True, verbose_name="Длительность (в минутах)")
    result = models.CharField(max_length=20, choices=INTERACTION_RESULT_CHOICES, verbose_name="Результат")
    notes = models.TextField(blank=True, null=True, verbose_name="Примечания")
    
    # Маркетолог, который взаимодействовал с лидом
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, 
                                   null=True, related_name="lead_interactions",
                                   verbose_name="Кем выполнено")
    
    # Файлы, связанные с взаимодействием (например, записи разговоров, скриншоты переписки)
    attachment = models.FileField(upload_to='crm/interactions/', blank=True, null=True, verbose_name="Вложение")
    
    class Meta:
        verbose_name = "Взаимодействие"
        verbose_name_plural = "Взаимодействия"
        ordering = ['-date_time']
    
    def __str__(self):
        return f"{self.lead.full_name} - {self.get_interaction_type_display()} ({self.date_time.strftime('%d.%m.%Y %H:%M')})"

# Модели для интеграции с Meta Business Suite
class MetaBusinessAccount(models.Model):
    """
    Модель для хранения данных о подключенном аккаунте Meta Business Suite
    """
    name = models.CharField(max_length=100, verbose_name="Название аккаунта")
    page_id = models.CharField(max_length=100, verbose_name="ID страницы")
    access_token = models.TextField(verbose_name="Токен доступа")
    token_expires_at = models.DateTimeField(verbose_name="Срок действия токена")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    
    # Связь с маркетологами, которые имеют доступ к этому аккаунту
    marketers = models.ManyToManyField(User, limit_choices_to={'user_type': 'marketer'}, 
                                     related_name="meta_accounts", verbose_name="Маркетологи")
    
    class Meta:
        verbose_name = "Аккаунт Meta Business"
        verbose_name_plural = "Аккаунты Meta Business"
    
    def __str__(self):
        return self.name
    
    @property
    def is_token_valid(self):
        """
        Проверяет, действителен ли токен доступа
        """
        return timezone.now() < self.token_expires_at

class SocialMessage(models.Model):
    """
    Модель для хранения сообщений из социальных сетей
    """
    MESSAGE_TYPES = (
        ('whatsapp', 'WhatsApp'),
        ('instagram', 'Instagram DM'),
        ('facebook', 'Facebook Messenger'),
    )
    
    MESSAGE_DIRECTION = (
        ('incoming', 'Входящее'),
        ('outgoing', 'Исходящее'),
    )
    
    platform = models.CharField(max_length=20, choices=MESSAGE_TYPES, verbose_name="Платформа")
    direction = models.CharField(max_length=10, choices=MESSAGE_DIRECTION, verbose_name="Направление")
    sender_id = models.CharField(max_length=100, verbose_name="ID отправителя")
    sender_name = models.CharField(max_length=100, blank=True, null=True, verbose_name="Имя отправителя")
    message_text = models.TextField(verbose_name="Текст сообщения")
    timestamp = models.DateTimeField(verbose_name="Время сообщения")
    is_read = models.BooleanField(default=False, verbose_name="Прочитано")
    
    # Связь с лидом (если сообщение привязано к лиду)
    lead = models.ForeignKey(Lead, null=True, blank=True, on_delete=models.SET_NULL, related_name="social_messages", verbose_name="Лид")
    
    # Связь с маркетологом, ответственным за обработку сообщения
    assigned_to = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, 
                                   limit_choices_to={'user_type': 'marketer'},
                                   related_name="assigned_messages", verbose_name="Назначено")
    
    # Метаданные сообщения (например, вложения, геолокация и т.д.)
    meta_data = models.JSONField(blank=True, null=True, verbose_name="Метаданные")
    
    class Meta:
        verbose_name = "Сообщение из соцсети"
        verbose_name_plural = "Сообщения из соцсетей"
        ordering = ['-timestamp']
    
    def __str__(self):
        direction_icon = "←" if self.direction == "incoming" else "→"
        return f"{self.get_platform_display()} {direction_icon} {self.sender_name or self.sender_id}: {self.message_text[:30]}..."

# Модели для кампаний
class Campaign(models.Model):
    """
    Модель для маркетинговых кампаний
    """
    CAMPAIGN_STATUS_CHOICES = (
        ('draft', 'Черновик'),
        ('scheduled', 'Запланирована'),
        ('active', 'Активна'),
        ('paused', 'Приостановлена'),
        ('completed', 'Завершена'),
        ('cancelled', 'Отменена'),
    )
    
    name = models.CharField(max_length=100, verbose_name="Название кампании")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    status = models.CharField(max_length=20, choices=CAMPAIGN_STATUS_CHOICES, default='draft', verbose_name="Статус")
    
    # Даты проведения кампании
    start_date = models.DateField(verbose_name="Дата начала")
    end_date = models.DateField(verbose_name="Дата окончания")
    
    # Бюджет кампании
    budget = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Бюджет")
    spent = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Потрачено")
    
    # Цели кампании
    leads_goal = models.PositiveIntegerField(verbose_name="Цель по лидам")
    conversion_goal = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Цель по конверсии (%)")
    
    # Ответственный маркетолог
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                              limit_choices_to={'user_type': 'marketer'},
                              related_name="managed_campaigns", verbose_name="Менеджер кампании")
    
    # Даты создания и обновления
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Кампания"
        verbose_name_plural = "Кампании"
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"
    
    @property
    def is_active(self):
        """
        Проверяет, активна ли кампания в текущий момент
        """
        today = timezone.now().date()
        return (self.status == 'active' and 
                self.start_date <= today <= self.end_date)
    
    @property
    def progress(self):
        """
        Возвращает прогресс кампании в процентах
        """
        if self.status == 'completed':
            return 100
        
        today = timezone.now().date()
        if today < self.start_date:
            return 0
        
        if today > self.end_date:
            return 100
        
        total_days = (self.end_date - self.start_date).days
        if total_days <= 0:
            return 100
        
        days_passed = (today - self.start_date).days
        return min(100, int((days_passed / total_days) * 100))
    
    @property
    def budget_spent_percentage(self):
        """
        Возвращает процент потраченного бюджета
        """
        if self.budget <= 0:
            return 0
        return min(100, int((self.spent / self.budget) * 100))

class CampaignChannel(models.Model):
    """
    Модель для каналов распространения кампании
    """
    CHANNEL_TYPE_CHOICES = (
        ('whatsapp', 'WhatsApp'),
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
        ('google', 'Google Ads'),
        ('email', 'Email рассылка'),
        ('sms', 'SMS рассылка'),
        ('offline', 'Офлайн реклама'),
        ('other', 'Другое'),
    )
    
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="channels", verbose_name="Кампания")
    channel_type = models.CharField(max_length=20, choices=CHANNEL_TYPE_CHOICES, verbose_name="Тип канала")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    budget = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Бюджет канала")
    spent = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Потрачено")
    
    # Метрики эффективности
    impressions = models.PositiveIntegerField(default=0, verbose_name="Показы")
    clicks = models.PositiveIntegerField(default=0, verbose_name="Клики")
    leads_generated = models.PositiveIntegerField(default=0, verbose_name="Сгенерировано лидов")
    
    class Meta:
        verbose_name = "Канал кампании"
        verbose_name_plural = "Каналы кампаний"
    
    def __str__(self):
        return f"{self.campaign.name} - {self.get_channel_type_display()}"
    
    @property
    def ctr(self):
        """
        Возвращает CTR (Click-Through Rate) в процентах
        """
        if self.impressions <= 0:
            return 0
        return round((self.clicks / self.impressions) * 100, 2)
    
    @property
    def cost_per_lead(self):
        """
        Возвращает стоимость привлечения одного лида
        """
        if self.leads_generated <= 0:
            return 0
        return round(self.spent / self.leads_generated, 2)
    
    @property
    def conversion_rate(self):
        """
        Возвращает конверсию из клика в лида в процентах
        """
        if self.clicks <= 0:
            return 0
        return round((self.leads_generated / self.clicks) * 100, 2)

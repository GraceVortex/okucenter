import os
import logging
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from accounts.models import User, Marketer

logger = logging.getLogger(__name__)

# Модели для контактов и компаний
class Company(models.Model):
    """
    Модель для хранения информации о компаниях-клиентах
    """
    COMPANY_TYPE_CHOICES = (
        ('client', 'Клиент'),
        ('partner', 'Партнер'),
        ('vendor', 'Поставщик'),
        ('other', 'Другое'),
    )
    
    name = models.CharField(max_length=200, verbose_name="Название компании")
    company_type = models.CharField(max_length=20, choices=COMPANY_TYPE_CHOICES, default='client', verbose_name="Тип компании")
    website = models.URLField(blank=True, null=True, verbose_name="Веб-сайт")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Телефон")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    address = models.TextField(blank=True, null=True, verbose_name="Адрес")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    
    # Ответственный сотрудник
    responsible = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name="responsible_for_companies", verbose_name="Ответственный")
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Компания"
        verbose_name_plural = "Компании"
        ordering = ['name']
    
    def __str__(self):
        return self.name

class Contact(models.Model):
    """
    Модель для хранения информации о контактах (клиентах и контактных лицах)
    """
    CONTACT_TYPE_CHOICES = (
        ('client', 'Клиент'),
        ('lead', 'Лид'),
        ('contact_person', 'Контактное лицо'),
        ('other', 'Другое'),
    )
    
    first_name = models.CharField(max_length=100, verbose_name="Имя")
    last_name = models.CharField(max_length=100, verbose_name="Фамилия")
    middle_name = models.CharField(max_length=100, blank=True, null=True, verbose_name="Отчество")
    contact_type = models.CharField(max_length=20, choices=CONTACT_TYPE_CHOICES, default='client', verbose_name="Тип контакта")
    
    # Контактная информация
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Телефон")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    position = models.CharField(max_length=100, blank=True, null=True, verbose_name="Должность")
    
    # Связь с компанией
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, 
                               related_name="contacts", verbose_name="Компания")
    
    # Ответственный сотрудник
    responsible = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name="responsible_for_contacts", verbose_name="Ответственный")
    
    # Дополнительная информация
    notes = models.TextField(blank=True, null=True, verbose_name="Примечания")
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Контакт"
        verbose_name_plural = "Контакты"
        ordering = ['last_name', 'first_name']
    
    def __str__(self):
        return f"{self.last_name} {self.first_name}"
    
    @property
    def full_name(self):
        """
        Возвращает полное имя контакта
        """
        if self.middle_name:
            return f"{self.last_name} {self.first_name} {self.middle_name}"
        return f"{self.last_name} {self.first_name}"

# Модели для воронки продаж
class Pipeline(models.Model):
    """
    Модель для хранения информации о воронках продаж
    """
    name = models.CharField(max_length=100, verbose_name="Название воронки")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Воронка продаж"
        verbose_name_plural = "Воронки продаж"
        ordering = ['name']
    
    def __str__(self):
        return self.name

class Stage(models.Model):
    """
    Модель для хранения информации об этапах воронки продаж
    """
    pipeline = models.ForeignKey(Pipeline, on_delete=models.CASCADE, related_name="stages", verbose_name="Воронка")
    name = models.CharField(max_length=100, verbose_name="Название этапа")
    order = models.PositiveSmallIntegerField(verbose_name="Порядок отображения")
    probability = models.PositiveSmallIntegerField(default=0, verbose_name="Вероятность закрытия (%)")
    color = models.CharField(max_length=20, default="#3498db", verbose_name="Цвет этапа")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Этап воронки"
        verbose_name_plural = "Этапы воронки"
        ordering = ['pipeline', 'order']
    
    def __str__(self):
        return f"{self.pipeline.name} - {self.name}"

class Deal(models.Model):
    """
    Модель для хранения информации о сделках
    """
    DEAL_STATUS_CHOICES = (
        ('open', 'Открыта'),
        ('won', 'Выиграна'),
        ('lost', 'Проиграна'),
    )
    
    title = models.CharField(max_length=200, verbose_name="Название сделки")
    pipeline = models.ForeignKey(Pipeline, on_delete=models.SET_NULL, null=True, related_name="deals", verbose_name="Воронка")
    stage = models.ForeignKey(Stage, on_delete=models.SET_NULL, null=True, related_name="deals", verbose_name="Этап")
    status = models.CharField(max_length=20, choices=DEAL_STATUS_CHOICES, default='open', verbose_name="Статус")
    
    # Связи с контактами и компаниями
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True, 
                               related_name="deals", verbose_name="Контакт")
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, 
                               related_name="deals", verbose_name="Компания")
    
    # Финансовая информация
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Сумма сделки")
    currency = models.CharField(max_length=3, default="KZT", verbose_name="Валюта")
    
    # Даты
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    closed_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата закрытия")
    expected_close_date = models.DateField(blank=True, null=True, verbose_name="Ожидаемая дата закрытия")
    
    # Ответственный сотрудник
    responsible = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name="responsible_for_deals", verbose_name="Ответственный")
    
    # Дополнительная информация
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    
    class Meta:
        verbose_name = "Сделка"
        verbose_name_plural = "Сделки"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        """
        Переопределяем метод save для установки даты закрытия при изменении статуса
        """
        if self.status in ['won', 'lost'] and not self.closed_at:
            self.closed_at = timezone.now()
        super().save(*args, **kwargs)

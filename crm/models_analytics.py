import logging
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from accounts.models import User

logger = logging.getLogger(__name__)

class Report(models.Model):
    """
    Модель для сохранения настроек отчетов
    """
    REPORT_TYPE_CHOICES = (
        ('sales', 'Продажи'),
        ('leads', 'Лиды'),
        ('activities', 'Активности'),
        ('conversion', 'Конверсия'),
        ('custom', 'Пользовательский'),
    )
    
    name = models.CharField(max_length=100, verbose_name="Название отчета")
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES, verbose_name="Тип отчета")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    
    # Настройки отчета в формате JSON
    settings = models.JSONField(default=dict, verbose_name="Настройки отчета")
    
    # Связь с пользователем
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_reports", 
                                  verbose_name="Создал")
    
    # Доступ к отчету
    is_public = models.BooleanField(default=False, verbose_name="Публичный отчет")
    shared_with = models.ManyToManyField(User, related_name="shared_reports", blank=True, 
                                       verbose_name="Доступен для")
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Отчет"
        verbose_name_plural = "Отчеты"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name

class Dashboard(models.Model):
    """
    Модель для сохранения настроек дашбордов
    """
    name = models.CharField(max_length=100, verbose_name="Название дашборда")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    
    # Настройки дашборда в формате JSON
    layout = models.JSONField(default=dict, verbose_name="Макет дашборда")
    
    # Связь с пользователем
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_dashboards", 
                                  verbose_name="Создал")
    
    # Доступ к дашборду
    is_public = models.BooleanField(default=False, verbose_name="Публичный дашборд")
    shared_with = models.ManyToManyField(User, related_name="shared_dashboards", blank=True, 
                                       verbose_name="Доступен для")
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Дашборд"
        verbose_name_plural = "Дашборды"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name

class DashboardWidget(models.Model):
    """
    Модель для виджетов на дашборде
    """
    WIDGET_TYPE_CHOICES = (
        ('chart', 'График'),
        ('counter', 'Счетчик'),
        ('table', 'Таблица'),
        ('funnel', 'Воронка'),
        ('custom', 'Пользовательский'),
    )
    
    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE, related_name="widgets", 
                                 verbose_name="Дашборд")
    name = models.CharField(max_length=100, verbose_name="Название виджета")
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPE_CHOICES, verbose_name="Тип виджета")
    
    # Настройки виджета в формате JSON
    settings = models.JSONField(default=dict, verbose_name="Настройки виджета")
    
    # Позиция на дашборде
    position_x = models.PositiveSmallIntegerField(default=0, verbose_name="Позиция X")
    position_y = models.PositiveSmallIntegerField(default=0, verbose_name="Позиция Y")
    width = models.PositiveSmallIntegerField(default=1, verbose_name="Ширина")
    height = models.PositiveSmallIntegerField(default=1, verbose_name="Высота")
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Виджет дашборда"
        verbose_name_plural = "Виджеты дашборда"
        ordering = ['dashboard', 'position_y', 'position_x']
    
    def __str__(self):
        return f"{self.dashboard.name} - {self.name}"

class SalesTarget(models.Model):
    """
    Модель для целей продаж
    """
    TARGET_TYPE_CHOICES = (
        ('revenue', 'Выручка'),
        ('deals_count', 'Количество сделок'),
        ('conversion_rate', 'Конверсия'),
        ('custom', 'Пользовательская'),
    )
    
    PERIOD_CHOICES = (
        ('day', 'День'),
        ('week', 'Неделя'),
        ('month', 'Месяц'),
        ('quarter', 'Квартал'),
        ('year', 'Год'),
        ('custom', 'Пользовательский'),
    )
    
    name = models.CharField(max_length=100, verbose_name="Название цели")
    target_type = models.CharField(max_length=20, choices=TARGET_TYPE_CHOICES, verbose_name="Тип цели")
    period = models.CharField(max_length=20, choices=PERIOD_CHOICES, verbose_name="Период")
    
    # Значение цели
    target_value = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Целевое значение")
    
    # Период действия цели
    start_date = models.DateField(verbose_name="Дата начала")
    end_date = models.DateField(verbose_name="Дата окончания")
    
    # Связь с пользователем
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sales_targets", 
                                   verbose_name="Ответственный")
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Цель продаж"
        verbose_name_plural = "Цели продаж"
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.name} ({self.get_period_display()}: {self.start_date} - {self.end_date})"
    
    @property
    def current_value(self):
        """
        Возвращает текущее значение для цели
        """
        # Логика расчета текущего значения в зависимости от типа цели
        # Это заглушка, которую нужно реализовать
        return 0
    
    @property
    def progress_percentage(self):
        """
        Возвращает процент выполнения цели
        """
        if self.target_value == 0:
            return 0
        return min(100, int((self.current_value / self.target_value) * 100))

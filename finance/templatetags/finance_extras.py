from django import template
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import re

register = template.Library()

@register.filter
def subtract(value, arg):
    """Вычитает arg из value."""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return value

@register.filter
def add_month(date_value):
    """
    Принимает объект даты или строку даты в формате 'dd.mm.yyyy' 
    и возвращает последний день месяца
    """
    try:
        # Проверяем, является ли входное значение строкой или объектом даты
        if isinstance(date_value, str):
            # Преобразуем строку в дату
            date_obj = datetime.strptime(date_value, '%d.%m.%Y')
        else:
            # Используем объект даты как есть
            date_obj = date_value
        
        # Получаем последний день месяца
        if date_obj.month == 12:
            last_day = datetime(date_obj.year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = datetime(date_obj.year, date_obj.month + 1, 1) - timedelta(days=1)
        
        # Возвращаем в формате строки
        return last_day.strftime('%d.%m.%Y')
    except:
        return date_value

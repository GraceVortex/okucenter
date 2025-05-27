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

@register.filter
def split(value, arg):
    """
    Разделяет строку по указанному разделителю и возвращает список.
    Пример использования: {{ value|split:"," }}
    """
    return value.split(arg)

@register.filter
def index(value, arg):
    """
    Возвращает элемент списка по указанному индексу.
    Пример использования: {{ value|index:0 }}
    """
    try:
        return value[int(arg)]
    except (IndexError, TypeError):
        return ''

@register.filter
def multiply(value, arg):
    """
    Умножает value на arg.
    Пример использования: {{ value|multiply:2 }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return value

@register.filter
def divide(value, arg):
    """
    Делит value на arg.
    Пример использования: {{ value|divide:2 }}
    """
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return value

from django import template

register = template.Library()

@register.filter
def split(value, delimiter):
    """
    Разделяет строку по указанному разделителю и возвращает список.
    Пример использования: {{ value|split:"/" }}
    """
    return value.split(delimiter)

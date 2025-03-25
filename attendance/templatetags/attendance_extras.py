from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Фильтр для получения значения из словаря по ключу в шаблонах.
    Пример использования: {{ marks|get_item:student.id }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)

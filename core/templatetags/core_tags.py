from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Получает элемент из словаря по ключу.
    Используется в шаблонах для доступа к элементам словаря.
    """
    return dictionary.get(key, None)

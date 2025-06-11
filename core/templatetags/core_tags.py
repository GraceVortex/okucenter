from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Получает элемент из словаря по ключу.
    Используется в шаблонах для доступа к элементам словаря.
    """
    return dictionary.get(key, None)

@register.filter
def abs(value):
    """
    Возвращает абсолютное значение числа.
    """
    try:
        return __builtins__['abs'](int(value))
    except (ValueError, TypeError):
        return value

@register.filter
def multiply(value, arg):
    """
    Умножает значение на аргумент.
    Пример использования: {{ value|multiply:arg }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def t(text):
    """
    Переводит текст на выбранный язык.
    Пример использования: {{ "Текст для перевода"|t }}
    """
    from django.template import RequestContext
    request = getattr(template.Variable('request'), '_resolve_lookup', lambda context: context['request'])({})
    
    # Получаем функцию перевода из контекста
    translate = getattr(request, 'translate', None)
    if translate:
        return translate(text)
    
    # Если функция перевода недоступна, пробуем получить перевод из словаря
    user_language = getattr(request, 'user_language', 'ru')
    all_translations = getattr(request, 'all_translations', {})
    
    if user_language == 'ru' or not all_translations:
        return text
    
    translations = all_translations.get(user_language, {})
    if text in translations:
        return translations[text]
    
    # Проверяем ключ в нижнем регистре
    key = text.lower().replace(' ', '_')
    if key in translations:
        return translations[key]
    
    return text

@register.simple_tag(takes_context=True)
def trans(context, text):
    """
    Переводит текст на выбранный язык.
    Пример использования: {% trans "Текст для перевода" %}
    """
    request = context.get('request')
    if not request:
        return text
    
    # Получаем функцию перевода из контекста
    translate = context.get('translate')
    if translate:
        return mark_safe(translate(text))
    
    # Если функция перевода недоступна, пробуем получить перевод из словаря
    user_language = context.get('user_language', 'ru')
    all_translations = context.get('all_translations', {})
    
    if user_language == 'ru' or not all_translations:
        return mark_safe(text)
    
    translations = all_translations.get(user_language, {})
    if text in translations:
        return mark_safe(translations[text])
    
    # Проверяем ключ в нижнем регистре
    key = text.lower().replace(' ', '_')
    if key in translations:
        return mark_safe(translations[key])
    
    return mark_safe(text)

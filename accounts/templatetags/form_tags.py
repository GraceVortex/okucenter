from django import template

register = template.Library()

@register.filter(name='add_class')
def add_class(value, arg):
    """
    Adds a CSS class to a form field.
    
    Usage:
    {{ form.field|add_class:"form-control" }}
    """
    css_classes = value.field.widget.attrs.get('class', '')
    if css_classes:
        css_classes = f"{css_classes} {arg}"
    else:
        css_classes = arg
    return value.as_widget(attrs={'class': css_classes})

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Gets an item from a dictionary by key.
    
    Usage:
    {{ dictionary|get_item:key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key, [])

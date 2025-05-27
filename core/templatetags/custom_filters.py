from django import template

register = template.Library()

@register.filter
def absolute(value):
    """Returns the absolute value of a number."""
    return abs(value) if value is not None else None

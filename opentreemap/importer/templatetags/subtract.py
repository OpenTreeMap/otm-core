from django.template import Library

register = Library()


@register.filter
def subtract(value, arg):
    return value - arg

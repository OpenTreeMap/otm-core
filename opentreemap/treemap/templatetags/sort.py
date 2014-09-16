from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()


@register.filter
@stringfilter
def reverse_if_current(sort_order, current_sort_order):
    if sort_order == current_sort_order:
        return '-' + sort_order
    return sort_order

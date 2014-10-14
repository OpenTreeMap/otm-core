from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()


@register.filter
@stringfilter
def reverse_if_current(field, current_sort_order):
    if field == current_sort_order:
        return '-' + field
    return field


@register.filter
@stringfilter
def sort_direction_if_current(field, current_sort_order):
    if field == current_sort_order:
        return 'ascending'
    elif '-' + field == current_sort_order:
        return 'descending'
    else:
        return ''

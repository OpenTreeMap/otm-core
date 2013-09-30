from django import template

import math

register = template.Library()


@register.filter
def to_circumference(diameter):
    if diameter:
        return diameter * math.pi
    else:
        return ''

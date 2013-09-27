from django import template

import math

register = template.Library()


@register.filter
def to_circumference(diameter):
    return diameter * math.pi

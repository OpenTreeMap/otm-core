from django import template
import locale

import math

register = template.Library()


@register.filter
def to_circumference(diameter):
    if diameter:
        # Have to format here instead of the template in order to turn off
        # thousands grouping. Not using Django's format to turn off grouping
        return locale.format('%.3f', diameter * math.pi, grouping=False)
    else:
        return ''

from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()


@register.filter
@stringfilter
def datepicker_format(date_format):
    """
    Converts a Django DATE_FORMAT to the one specified at:
    https://github.com/eternicode/bootstrap-datepicker#format
    'D' and 'M' have the same meaning in both
    """
    date_format = date_format.replace('d', 'dd')
    date_format = date_format.replace('j', 'd')
    date_format = date_format.replace('l', 'DD')
    date_format = date_format.replace('m', 'mm')
    date_format = date_format.replace('n', 'm')
    date_format = date_format.replace('F', 'MM')
    date_format = date_format.replace('E', 'MM')  # Locale specific text month
    date_format = date_format.replace('y', 'yy')
    date_format = date_format.replace('Y', 'yyyy')

    return date_format

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


@register.filter
@stringfilter
def moment_format(date_format):
    """
    Converts a Django DATE_FORMAT to the one specified at:
    http://momentjs.com/docs/#/displaying/
    """
    conv_dict = {
        'j': 'D',
        'd': 'DD',
        'D': 'ddd',
        'l': 'dddd',
        'n': 'M',
        'm': 'MM',
        'N': 'MMM',
        'M': 'MMM',
        'F': 'MMMM',
        'E': 'MMMM',  # Locale text month,
        'y': 'YY',
        'Y': 'YYYY'
    }
    moment_format = ''.join(conv_dict.get(ch, ch) for ch in date_format)
    return moment_format

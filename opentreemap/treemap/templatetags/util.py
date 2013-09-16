from django import template


register = template.Library()


register.filter('get', lambda a, b: a[b])

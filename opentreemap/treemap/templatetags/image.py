from django import template
from django.core.files.storage import default_storage


register = template.Library()


register.filter('image_to_url', lambda name: default_storage.url(name))

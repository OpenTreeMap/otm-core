# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django import template
from django.core.urlresolvers import reverse

register = template.Library()


@register.filter
def is_current_view(request, views):
    views = views.split(' ')
    for view in views:
        url = reverse(view, kwargs={
            'instance_url_name': request.instance.url_name})
        if request.path == url:
            return True

    return False

# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import include, url
from django.template import Template
from django.template.response import TemplateResponse

from opentreemap import urls


def last_instance(request):
    """
    Returns the PK of the last instance saved in session
    """
    return TemplateResponse(request, Template("{{ last_instance.pk }}"))


urlpatterns = [
    url(r'^test-last-instance$', last_instance),
    url(r'', include(urls))
]

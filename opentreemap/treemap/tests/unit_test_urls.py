# -*- coding: utf-8 -*-




from django.conf.urls import include, url
from django.template import Template, RequestContext
from django.template.response import HttpResponse

from opentreemap import urls


def last_instance(request):
    """
    Returns the PK of the last instance saved in session
    """
    template = Template("{{ last_instance.pk }}")
    return HttpResponse(template.render(RequestContext(request, {})))


urlpatterns = [
    url(r'^test-last-instance$', last_instance),
    url(r'', include(urls))
]

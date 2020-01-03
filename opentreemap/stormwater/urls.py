# -*- coding: utf-8 -*-




from django.conf.urls import url

from opentreemap.urls import instance_pattern
from stormwater import routes


urlpatterns = [
    url(r'%s/polygon-for-point/$' % instance_pattern,
        routes.polygon_for_point, name='polygon_for_point'),
]

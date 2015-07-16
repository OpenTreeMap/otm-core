# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import patterns, url

from opentreemap.urls import instance_pattern
from stormwater import routes


urlpatterns = patterns(
    '',
    url(r'%s/polygon-for-point/$' % instance_pattern,
        routes.polygon_for_point, name='polygon_for_point'),
)

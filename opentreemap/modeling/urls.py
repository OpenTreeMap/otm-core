# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import url

from opentreemap.urls import instance_pattern
from modeling.routes import (run_model_view,
                             modeling_view,
                             get_boundaries_at_point_view,
                             plans_view, plan_view)


urlpatterns = [
    url(r'%s/modeling/$' % instance_pattern, modeling_view,
        name='model_trees'),
    url(r'%s/modeling/plans/$' % instance_pattern, plans_view,
        name='plans'),
    url(r'%s/modeling/plans/(?P<plan_id>\d+)/$' % instance_pattern,
        plan_view, name='plan'),
    url(r'%s/modeling/boundaries-at-point/$' % instance_pattern,
        get_boundaries_at_point_view, name='boundaries_at_point'),
    url(r'%s/modeling/run/$' % instance_pattern, run_model_view,
        name='run_model'),
]

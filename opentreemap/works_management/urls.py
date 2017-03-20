# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import patterns, url

from works_management import routes


urlpatterns = patterns(
    '',
    url(r'^work-orders/$', routes.work_orders, name='work_orders'),
    url(r'^create-tasks/$', routes.create_tasks, name='create_tasks'),
)

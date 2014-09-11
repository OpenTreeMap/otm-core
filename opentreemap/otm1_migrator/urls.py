# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import patterns, url

from views import user_csv_endpoint

urlpatterns = patterns(
    '',
    url(r'^csv/$', user_csv_endpoint, name='otm1-migrator-user-csv')
)

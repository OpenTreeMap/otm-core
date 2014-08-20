# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import patterns, url

from otm_comments.views import comments_csv_endpoint


urlpatterns = patterns(
    '',
    url(r'^csv/$', comments_csv_endpoint, name='comments-csv')
)

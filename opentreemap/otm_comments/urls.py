# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import url

from otm_comments.views import (comments_csv_endpoint, flag_endpoint,
                                unflag_endpoint, hide_flags_endpoint,
                                archive_endpoint, unarchive_endpoint,
                                hide_endpoint, show_endpoint,
                                comment_moderation_partial_endpoint)

urlpatterns = [
    url(r'^(?P<comment_id>\d+)/flag/$', flag_endpoint, name='flag-comment'),
    url(r'^(?P<comment_id>\d+)/unflag/$', unflag_endpoint,
        name='unflag-comment'),
    url(r'^hide-flags/$', hide_flags_endpoint, name='hide-comment-flags'),
    url(r'^archive/$', archive_endpoint, name='archive-comments'),
    url(r'^unarchive/$', unarchive_endpoint, name='unarchive-comments'),
    url(r'^hide/$', hide_endpoint, name='hide-comments'),
    url(r'^show/$', show_endpoint, name='show-comments'),
    url(r'^csv/$', comments_csv_endpoint, name='comments-csv'),
    url(r'^moderation-table/$', comment_moderation_partial_endpoint,
        name='comment_moderation')
]

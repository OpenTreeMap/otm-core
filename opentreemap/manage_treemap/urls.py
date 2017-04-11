from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import patterns, url

from manage_treemap import routes

urlpatterns = patterns(
    '',
    url(r'^$', routes.management, name='management'),
)

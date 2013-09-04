from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import patterns, url
from geocode.views import geocode_view

urlpatterns = patterns(
    '', url(r'^geocode$', geocode_view, name='geocode'))

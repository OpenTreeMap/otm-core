from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import patterns, url

from ecobenefits.views import tree_benefits

urlpatterns = patterns(
    '',
    url(r'^benefit/tree/(?P<tree_id>\d+)/$', tree_benefits),
)

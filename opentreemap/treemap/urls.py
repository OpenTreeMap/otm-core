from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import patterns, url

from treemap.views import boundary_to_geojson, index, trees,\
    plot_detail, settings_js, audits, search_tree_benefits,\
    boundary_autocomplete, species_list

urlpatterns = patterns(
    '',
    url(r'^$', index),
    url(r'^boundaries/(?P<boundary_id>\d+)/geojson/$', boundary_to_geojson),
    url(r'^boundaries/autocomplete$', boundary_autocomplete),
    url(r'^species/$', species_list),
    url(r'^recentedits', audits),
    url(r'^trees/$', trees),
    url(r'^trees/(?P<plot_id>\d+)/$', plot_detail),
    url(r'^config/settings.js$', settings_js),
    url(r'^benefit/search$', search_tree_benefits),
)

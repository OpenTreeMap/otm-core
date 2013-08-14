from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import patterns, url

from treemap.views import (boundary_to_geojson_view, index_view, map_view,
                           plot_detail_view, instance_settings_js_view,
                           audits_view, search_tree_benefits_view,
                           species_list_view, boundary_autocomplete_view,
                           instance_user_view, plot_popup_view,
                           instance_user_audits, plot_accordian_view)

# Testing notes:
# We want to test that every URL succeeds (200) or fails with bad data (404).
# If you add/remove/modify a URL, please update the corresponding test(s)
# in treemap/tests/urls.py

urlpatterns = patterns(
    '',
    url(r'^$', index_view),
    url(r'^boundaries/(?P<boundary_id>\d+)/geojson/$',
        boundary_to_geojson_view),
    url(r'^boundaries/$', boundary_autocomplete_view),
    url(r'^recent_edits', audits_view, name='recent_edits'),
    url(r'^species/$', species_list_view),
    url(r'^map/$', map_view, name='map'),
    url(r'^plots/(?P<plot_id>\d+)/$', plot_detail_view, name='plot_detail'),
    url(r'^plots/(?P<plot_id>\d+)/detail$', plot_accordian_view,
        name='plot_accordian'),
    url(r'^plots/(?P<plot_id>\d+)/popup$', plot_popup_view),
    url(r'^config/settings.js$', instance_settings_js_view),
    url(r'^benefit/search$', search_tree_benefits_view),
    url(r'^users/(?P<username>\w+)/?$', instance_user_view),
    url(r'^users/(?P<username>\w+)/recent_edits/?$', instance_user_audits),
)

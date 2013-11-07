# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import patterns, url

from opentreemap.util import route

from treemap.views import (boundary_to_geojson_view, index_view, map_view,
                           get_plot_detail_view, update_plot_detail_view,
                           instance_settings_js_view, edits_view,
                           search_tree_benefits_view, species_list_view,
                           boundary_autocomplete_view, instance_user_view,
                           plot_popup_view, instance_user_audits,
                           plot_accordion_view, add_plot_view,
                           add_tree_photo_endpoint, photo_review_endpoint,
                           approve_or_reject_photo_view, next_photo_endpoint,
                           photo_review_partial_endpoint, get_plot_eco_view,
                           edit_plot_detail_view, static_page_view,
                           get_plot_sidebar_view)

# Testing notes:
# We want to test that every URL succeeds (200) or fails with bad data (404).
# If you add/remove/modify a URL, please update the corresponding test(s)
# in treemap/tests/urls.py

USERNAME_PATTERN = r'(?P<username>[\w.@+-]+)'

urlpatterns = patterns(
    '',
    url(r'^$', index_view),
    url(r'page/(?P<page>[a-zA-Z0-9]+)/$',
        static_page_view, name='static_page'),
    url(r'^boundaries/(?P<boundary_id>\d+)/geojson/$',
        boundary_to_geojson_view),
    url(r'^boundaries/$', boundary_autocomplete_view),
    url(r'^edits/$', edits_view, name='edits'),
    url(r'^photo_review/$', photo_review_endpoint),
    url(r'^photo_review/next$', next_photo_endpoint),
    url(r'^photo_review/partial$', photo_review_partial_endpoint),
    url(r'^species/$', species_list_view),
    url(r'^map/$', map_view, name='map'),
    url(r'^plots/(?P<plot_id>\d+)/$',
        route(GET=get_plot_detail_view, PUT=update_plot_detail_view),
        name='plot_detail'),
    url(r'^plots/(?P<plot_id>\d+)/eco$',
        get_plot_eco_view),
    url(r'^plots/(?P<plot_id>\d+)/sidebar$',
        get_plot_sidebar_view),
    url(r'^plots/(?P<plot_id>\d+)/trees/(?P<tree_id>\d+)/eco$',
        get_plot_eco_view),
    url(r'^plots/(?P<plot_id>\d+)/(?P<edit>edit)$',
        edit_plot_detail_view, name='plot_detail_edit'),
    url(r'^plots/(?P<plot_id>\d+)/trees/(?P<tree_id>\d+)/$',
        route(GET=get_plot_detail_view, PUT=update_plot_detail_view),
        name='tree_detail'),
    url(r'^plots/(?P<plot_id>\d+)/detail$', plot_accordion_view,
        name='plot_accordion'),
    url(r'^plots/(?P<plot_id>\d+)/popup$', plot_popup_view),
    url(r'^plots/$', route(POST=add_plot_view)),
    url(r'^plots/(?P<plot_id>\d+)/photo$',
        add_tree_photo_endpoint, name='add_photo_to_plot'),
    url(r'^plots/(?P<plot_id>\d+)/tree/(?P<tree_id>\d+)/photo$',
        add_tree_photo_endpoint, name='add_photo_to_tree'),
    url('^plots/(?P<plot_id>\d+)/tree/'
        '(?P<tree_id>\d+)/photo/(?P<photo_id>\d+)/'
        '(?P<action>(approve)|(reject))$',
        approve_or_reject_photo_view, name='approve_or_reject_photo'),
    url(r'^config/settings.js$',
        instance_settings_js_view, name='settings'),
    url(r'^benefit/search$', search_tree_benefits_view),
    url(r'^users/%s/$' % USERNAME_PATTERN, instance_user_view),
    url(r'^users/%s/edits/$' % USERNAME_PATTERN, instance_user_audits),
)

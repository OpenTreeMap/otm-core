# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import patterns, url

from opentreemap.util import route

from treemap.views import (boundary_to_geojson_view, index_view, map_view,
                           delete_tree_view, update_map_feature_detail_view,
                           delete_map_feature_view, instance_settings_js_view,
                           get_map_feature_detail_view, edits_view,
                           search_tree_benefits_view, species_list_view,
                           boundary_autocomplete_view, instance_user_view,
                           map_feature_popup_view, instance_user_audits_view,
                           plot_accordion_view, add_map_feature_view,
                           add_tree_photo_endpoint, photo_review_endpoint,
                           photo_review_partial_endpoint,
                           approve_or_reject_photo_view, next_photo_endpoint,
                           get_plot_eco_view, edit_plot_detail_view,
                           static_page_view, get_map_feature_sidebar_view,
                           tree_detail_view, get_map_feature_add_view,
                           add_map_feature_photo_endpoint)

# Testing notes:
# We want to test that every URL succeeds (200) or fails with bad data (404).
# If you add/remove/modify a URL, please update the corresponding test(s)
# in treemap/tests/urls.py

USERNAME_PATTERN = r'(?P<username>[\w.@+-]+)'

urlpatterns = patterns(
    '',
    url(r'^$', index_view),
    url(r'page/(?P<page>[a-zA-Z0-9 ]+)/$',
        static_page_view, name='static_page'),
    url(r'^boundaries/(?P<boundary_id>\d+)/geojson/$',
        boundary_to_geojson_view),
    url(r'^boundaries/$', boundary_autocomplete_view),
    url(r'^edits/$', edits_view, name='edits'),
    url(r'^photo_review_full/$', photo_review_endpoint),
    url(r'^photo_review/$', photo_review_partial_endpoint,
        name='photo_review'),
    url(r'^photo_review/next$', next_photo_endpoint, name='photo_review_next'),
    url(r'^species/$', species_list_view),
    url(r'^map/$', map_view, name='map'),

    url(r'^features/(?P<feature_id>\d+)/$',
        route(GET=get_map_feature_detail_view,
              PUT=update_map_feature_detail_view,
              DELETE=delete_map_feature_view),
        name='map_feature_detail'),
    url(r'^features/(?P<type>\w+)/$',
        route(GET=get_map_feature_add_view, POST=add_map_feature_view),
        name='add_map_feature'),
    url(r'^features/(?P<feature_id>\d+)/(?P<edit>edit)$',
        edit_plot_detail_view, name='map_feature_detail_edit'),
    url(r'^features/(?P<feature_id>\d+)/popup$',
        map_feature_popup_view, name='map_feature_popup'),
    url(r'^features/(?P<feature_id>\d+)/trees/(?P<tree_id>\d+)/$',
        route(DELETE=delete_tree_view)),
    url(r'^features/(?P<feature_id>\d+)/sidebar$',
        get_map_feature_sidebar_view, name='map_feature_sidebar'),
    url(r'^features/(?P<feature_id>\d+)/photo$',
        add_map_feature_photo_endpoint, name='add_photo_to_map_feature'),

    url(r'^plots/$', route(POST=add_map_feature_view), name='add_plot'),
    url(r'^plots/(?P<feature_id>\d+)/detail$',
        plot_accordion_view, name='plot_accordion'),
    url(r'^plots/(?P<feature_id>\d+)/eco$',
        get_plot_eco_view, name='plot_eco'),
    url(r'^plots/(?P<feature_id>\d+)/trees/(?P<tree_id>\d+)/eco$',
        get_plot_eco_view, name='tree_eco'),
    url(r'^plots/(?P<feature_id>\d+)/trees/(?P<tree_id>\d+)/$',
        tree_detail_view, name='tree_detail'),

    url(r'^plots/(?P<feature_id>\d+)/photo$',
        add_tree_photo_endpoint, name='add_photo_to_plot'),
    url(r'^plots/(?P<feature_id>\d+)/tree/(?P<tree_id>\d+)/photo$',
        add_tree_photo_endpoint, name='add_photo_to_tree'),
    url('^plots/(?P<feature_id>\d+)/tree/'
        '(?P<tree_id>\d+)/photo/(?P<photo_id>\d+)/'
        '(?P<action>(approve)|(reject))$',
        approve_or_reject_photo_view, name='approve_or_reject_photo'),

    url(r'^config/settings.js$',
        instance_settings_js_view, name='settings'),
    url(r'^benefit/search$', search_tree_benefits_view),
    url(r'^users/%s/$' % USERNAME_PATTERN, instance_user_view,
        name="user_profile"),
    url(r'^users/%s/edits/$' % USERNAME_PATTERN, instance_user_audits_view),
)

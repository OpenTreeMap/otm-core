# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import patterns, url

from django_tinsel.decorators import route

from treemap.views import (boundary_to_geojson_view, index_view, map_view,
                           delete_tree_view, instance_settings_js_view,
                           edits_view,
                           search_tree_benefits_view, species_list_view,
                           boundary_autocomplete_view, instance_user_view,
                           map_feature_popup_view, instance_user_audits_view,
                           map_feature_accordion_view,
                           add_tree_photo_endpoint, photo_review_endpoint,
                           photo_review_partial_endpoint,
                           approve_or_reject_photo_view, next_photo_endpoint,
                           get_plot_eco_view, edit_plot_detail_view,
                           static_page_view, get_map_feature_sidebar_view,
                           tree_detail_view, add_map_feature_photo_endpoint,
                           map_feature_detail_view, map_feature_add_view,
                           rotate_map_feature_photo_endpoint)

# Testing notes:
# We want to test that every URL succeeds (200) or fails with bad data (404).
# If you add/remove/modify a URL, please update the corresponding test(s)
# in treemap/tests/urls.py

USERNAME_PATTERN = r'(?P<username>[\w.@+-]+)'

urlpatterns = patterns(
    '',
    url(r'^$', index_view, name='instance_index_view'),
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
    url('^features/(?P<feature_id>\d+)/photo/(?P<photo_id>\d+)/'
        '(?P<action>(approve)|(reject))$',
        approve_or_reject_photo_view, name='approve_or_reject_photo'),
    url(r'^species/$', species_list_view),
    url(r'^map/$', map_view, name='map'),

    url(r'^features/(?P<feature_id>\d+)/$',
        map_feature_detail_view, name='map_feature_detail'),
    url(r'^features/(?P<type>\w+)/$',
        map_feature_add_view, name='add_map_feature'),
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
    url(r'^features/(?P<feature_id>\d+)/detail$',
        map_feature_accordion_view, name='map_feature_accordion'),
    url('^features/(?P<feature_id>\d+)/photo/(?P<photo_id>\d+)$',
        rotate_map_feature_photo_endpoint, name='rotate_photo'),

    url(r'^plots/$', route(POST=map_feature_add_view), name='add_plot'),
    url(r'^plots/(?P<feature_id>\d+)/eco$',
        get_plot_eco_view, name='plot_eco'),
    url(r'^plots/(?P<feature_id>\d+)/trees/(?P<tree_id>\d+)/eco$',
        get_plot_eco_view, name='tree_eco'),
    url(r'^plots/(?P<feature_id>\d+)/trees/(?P<tree_id>\d+)/$',
        tree_detail_view, name='tree_detail'),

    # TODO: this duplication exists in multiple places.
    # we make two endpoints for 'plots/<id>/tree/<id>/' and 'plots/<id>/'
    # to simplify the client, because the plot_detail page itself can
    # have two different urls, and it makes it easier to say stuff like
    # url = document.url = '/photos' or whatever. We can find a higher level
    # way to handle this duplication and reduce the total number of endpoints
    # for great good.
    url(r'^plots/(?P<feature_id>\d+)/photo$',
        add_tree_photo_endpoint, name='add_photo_to_plot'),
    url(r'^plots/(?P<feature_id>\d+)/tree/(?P<tree_id>\d+)/photo$',
        add_tree_photo_endpoint, name='add_photo_to_tree'),

    url(r'^config/settings.js$',
        instance_settings_js_view, name='settings'),
    url(r'^benefit/search$', search_tree_benefits_view),
    url(r'^users/%s/$' % USERNAME_PATTERN, instance_user_view,
        name="user_profile"),
    url(r'^users/%s/edits/$' % USERNAME_PATTERN, instance_user_audits_view),
)

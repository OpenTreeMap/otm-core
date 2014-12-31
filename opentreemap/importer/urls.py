# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import patterns, url

from importer.views import (
    start_import_endpoint, update_row_endpoint, export_all_species,
    export_single_species_import, export_single_tree_import, merge_species,
    commit_endpoint, counts, show_import_status_endpoint, cancel_endpoint,
    list_imports_endpoint, refresh_imports_endpoint, solve_endpoint)

from treemap.plugin import feature_enabled

_type_pattern = '(?P<import_type>(species|tree))'
_ie_pattern = '(?P<import_event_id>\d+)'
_import_api_pattern = _type_pattern + '/' + _ie_pattern


urlpatterns = patterns(
    '',
    url(r'^$', list_imports_endpoint, name='list_imports'),
    url(r'^refresh$', refresh_imports_endpoint, name='refresh_imports'),
    url(r'^start_import$', start_import_endpoint, name='start_import'),
    url(r'^status/%s/' % _import_api_pattern, show_import_status_endpoint,
        name='status'),
    url(r'^cancel/%s/$' % _import_api_pattern, cancel_endpoint, name='cancel'),
    url(r'^species/solve(?P<import_event_id>\d+)/(?P<row_index>\d+)/$',
        solve_endpoint, name='solve'),
    url(r'^update/%s/(?P<row_id>\d+)/$' % _type_pattern,
        update_row_endpoint, name='update_row'),
    url(r'^commit/%s/$' % _import_api_pattern, commit_endpoint, name='commit'),

    url(r'^export/species/all', export_all_species, name='export_all_species'),
    url(r'^export/species/(?P<import_event_id>\d+)$',
        export_single_species_import, name='export_single_species_import'),
    url(r'^export/tree/(?P<import_event_id>\d+)$', export_single_tree_import,
        name='export_single_tree_import'),

    # API
    url(r'^api/merge$', merge_species, name='merge'),
    url(r'^api/counts', counts, name='counts'),
)

if not feature_enabled(None, 'bulk_upload'):
    urlpatterns = patterns('')

# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls.defaults import patterns, url
from django.contrib import admin

from importer.views import (
    list_imports, create, show_tree_import_status, show_species_import_status,
    update_row, export_all_species, export_single_species_import,
    export_single_tree_import, merge_species, results, commit, update, solve,
    counts, find_similar_species)

admin.autodiscover()


_import_api_pattern = r'(?P<import_type>[a-z]+)/(?P<import_event_id>\d+)'


urlpatterns = patterns(
    'importer.views',
    url(r'^$', list_imports, name='list_imports'),
    url(r'^create$', create, name='create'),
    url(r'^status/tree/(?P<import_event_id>\d+)$', show_tree_import_status,
        name='show_tree_import_status'),
    url(r'^status/species/(?P<import_event_id>\d+)$',
        show_species_import_status, name='show_species_import_status'),
    url(r'^update/(?P<import_event_row_id>\d+)$', update_row,
        name='update_row'),

    url(r'^export/species/all', export_all_species, name='export_all_species'),
    url(r'^export/species/(?P<import_event_id>\d+)$',
        export_single_species_import, name='export_single_species_import'),
    url(r'^export/tree/(?P<import_event_id>\d+)$', export_single_tree_import,
        name='export_single_tree_import'),

    # API
    url(r'^api/merge$', merge_species, name='merge'),
    url(r'^api/%s/results/(?P<subtype>[a-zA-Z]+)$' % _import_api_pattern,
        results, name='results'),
    url(r'^api/%s/commit$' % _import_api_pattern, commit, name='commit'),
    url(r'^api/%s/update$' % _import_api_pattern, update, name='update'),
    url(r'^api/species/(?P<import_event_id>\d+)/(?P<import_row_idx>\d+)/solve$',  # NOQA
        solve, name='solve'),
    url(r'^api/counts', counts, name='counts'),
    url(r'^api/species/similar', find_similar_species,
        name='find_similar_species'),
)

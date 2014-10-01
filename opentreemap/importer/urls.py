from django.conf.urls.defaults import *

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns(
    'importer.views',
    url(r'^$', 'list_imports', name='list_imports'),
    url(r'^create$', 'create', name='create'),
    url(r'^status/tree/(?P<import_event_id>\d+)$', 'show_tree_import_status', name='show_tree_import_status'),
    url(r'^status/species/(?P<import_event_id>\d+)$', 'show_species_import_status', name='show_species_import_status'),
    url(r'^update/(?P<import_event_row_id>\d+)$', 'update_row', name='update_row'),

    url(r'^export/species/all', 'export_all_species', name='export_all_species'),
    url(r'^export/species/(?P<import_event_id>\d+)$', 'export_single_species_import', name='export_single_species_import'),
    url(r'^export/tree/(?P<import_event_id>\d+)$', 'export_single_tree_import', name='export_single_tree_import'),

    # API
    url(r'^api/merge$', 'merge_species', name='merge'),
    url(r'^api/(?P<import_type>[a-z]+)/(?P<import_event_id>\d+)/results/(?P<subtype>[a-zA-Z]+)$', 'results', name='results'),
    url(r'^api/(?P<import_type>[a-z]+)/(?P<import_event_id>\d+)/commit$', 'commit', name='commit'),
    url(r'^api/(?P<import_type>[a-z]+)/(?P<import_event_id>\d+)/update$', 'update', name='update'),
    url(r'^api/species/(?P<import_event_id>\d+)/(?P<import_row_idx>\d+)/solve$', 'solve', name='solve'),
    url(r'^api/counts', 'counts', name='counts'),
    url(r'^api/species/similar', 'find_similar_species', name='find_similar_species'),
)

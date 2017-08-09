# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import url

from importer import routes

_type_pattern = '(?P<import_type>(species|tree))'
_ie_pattern = '(?P<import_event_id>\d+)'
_import_api_pattern = _type_pattern + '/' + _ie_pattern


urlpatterns = [
    url(r'^$', routes.list_imports, name='list_imports'),
    url(r'^table/(?P<table_name>\w+)/$', routes.get_import_table,
        name='get_import_table'),
    url(r'^start_import/$', routes.start_import, name='start_import'),
    url(r'^status/%s/' % _import_api_pattern, routes.show_import_status,
        name='status'),
    url(r'^cancel/%s/$' % _import_api_pattern, routes.cancel, name='cancel'),
    url(r'^species/solve(?P<import_event_id>\d+)/(?P<row_index>\d+)/$',
        routes.solve, name='solve'),
    url(r'^update/%s/(?P<row_id>\d+)/$' % _type_pattern,
        routes.update_row, name='update_row'),
    url(r'^commit/%s/$' % _import_api_pattern, routes.commit, name='commit'),

    url(r'^export/species/all', routes.export_all_species,
        name='export_all_species'),
    url(r'^export/%s/$' % _import_api_pattern, routes.export_single_import,
        name='export_single_import'),
    url(r'^download_template/%s/$' % _type_pattern,
        routes.download_import_template,
        name='download_import_template'),

    # API
    url(r'^api/merge$', routes.merge_species, name='merge'),
]

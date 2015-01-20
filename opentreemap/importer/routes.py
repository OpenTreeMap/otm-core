# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django_tinsel.utils import decorate as do
from django_tinsel.decorators import render_template, json_api_call

from treemap.decorators import (admin_instance_request, require_http_method,
                                requires_feature)

from importer import views


def _api_call(verb, view_fn):
    return do(
        admin_instance_request,
        requires_feature('bulk_upload'),
        require_http_method(verb),
        view_fn)


def _template_api_call(verb, template, view_fn):
    templated_view = render_template(template)(view_fn)
    return _api_call(verb, templated_view)


list_imports = _template_api_call(
    'GET', 'importer/partials/imports.html', views.list_imports)

refresh_imports = _template_api_call(
    'GET', 'importer/partials/import_tables.html', views.list_imports)

start_import = _template_api_call(
    'POST', 'importer/partials/imports.html', views.start_import)

cancel = _template_api_call(
    'GET', 'importer/partials/imports.html', views.cancel)

solve = _template_api_call(
    'POST', 'importer/partials/row_status.html', views.solve)

commit = _template_api_call(
    'GET', 'importer/partials/imports.html', views.commit)

show_import_status = _api_call('GET', views.show_import_status)

update_row = _template_api_call(
    'POST', 'importer/partials/row_status.html', views.update_row)

export_all_species = _api_call('GET', json_api_call(views.export_all_species))

export_single_species_import = _api_call(
    'GET', json_api_call(views.export_single_species_import))

export_single_tree_import = _api_call(
    'GET', json_api_call(views.export_single_tree_import))

merge_species = _api_call('POST', views.merge_species)

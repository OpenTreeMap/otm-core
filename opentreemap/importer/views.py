# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import csv
import json
import io
from copy import copy

from django.db import transaction
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from django.core.paginator import Paginator, Page
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.utils.translation import ugettext as trans

from django.contrib.auth.decorators import login_required

from django_tinsel.utils import decorate as do
from django_tinsel.decorators import render_template

from treemap.models import Species, Tree, User
from treemap.decorators import (admin_instance_request, require_http_method,
                                requires_feature)
from treemap.units import get_conversion_factor

from importer.models import GenericImportEvent, GenericImportRow
from importer.trees import TreeImportEvent, TreeImportRow
from importer.species import SpeciesImportEvent, SpeciesImportRow
from importer.tasks import (run_import_event_validation, commit_import_event,
                            get_import_event_model, get_import_row_model)
from importer import errors, fields
from importer.util import lowerkeys


def _find_similar_species(target, instance):
    species = Species.objects\
                     .filter(instance=instance)\
                     .extra(
                         select={
                             'l': ("levenshtein(genus || ' ' || species || "
                                   "' ' || cultivar || ' ' || "
                                   "other_part_of_name, %s)")
                         },
                         select_params=(target,))\
                     .order_by('l')[0:2]  # Take top 2

    output = [{fields.trees.GENUS: s.genus,
               fields.trees.SPECIES: s.species,
               fields.trees.CULTIVAR: s.cultivar,
               fields.trees.OTHER_PART_OF_NAME: s.other_part_of_name,
               'display_name': s.display_name,
               'pk': s.pk} for s in species]

    return output


def counts(request, instance):
    active_trees = TreeImportEvent\
        .objects\
        .filter(instance=instance)\
        .order_by('id')\
        .exclude(status=GenericImportEvent.FINISHED_CREATING)\
        .exclude(status=GenericImportEvent.FINISHED_VERIFICATION)\
        .exclude(status=GenericImportEvent.FAILED_FILE_VERIFICATION)

    active_species = SpeciesImportEvent\
        .objects\
        .filter(instance=instance)\
        .order_by('id')\
        .exclude(status=GenericImportEvent.FINISHED_CREATING)\
        .exclude(status=GenericImportEvent.FINISHED_VERIFICATION)\
        .exclude(status=GenericImportEvent.FAILED_FILE_VERIFICATION)

    output = {}
    output['trees'] = {t.pk: t.row_counts_by_status() for t in active_trees}
    output['species'] = {s.pk: s.row_counts_by_status()
                         for s in active_species}

    return HttpResponse(json.dumps(output), content_type='application/json')


def start_import(request, instance):
    import_type = request.REQUEST['type']
    if import_type == TreeImportEvent.import_type:
        kwargs = {
            'plot_length_conversion_factor':
            float(request.REQUEST.get('unit_plot_length', 1.0)),

            'plot_width_conversion_factor':
            float(request.REQUEST.get('unit_plot_width', 1.0)),

            'diameter_conversion_factor':
            float(request.REQUEST.get('unit_diameter', 1.0)),

            'tree_height_conversion_factor':
            float(request.REQUEST.get('unit_tree_height', 1.0)),

            'canopy_height_conversion_factor':
            float(request.REQUEST.get('unit_canopy_height', 1.0))
        }
    else:
        kwargs = {
            'max_diameter_conversion_factor':
            get_conversion_factor(instance, 'tree', 'diameter'),
            'max_tree_height_conversion_factor':
            get_conversion_factor(instance, 'tree', 'height')
        }
    process_csv(request, instance, import_type, **kwargs)

    return list_imports(request, instance)


def list_imports(request, instance):
    finished = GenericImportEvent.FINISHED_CREATING

    trees = TreeImportEvent.objects.filter(instance=instance).order_by('id')
    active_trees = trees.exclude(status=finished)
    finished_trees = trees.filter(status=finished)

    species = SpeciesImportEvent.objects\
        .filter(instance=instance)\
        .order_by('id')
    active_species = species.exclude(status=finished)
    finished_species = species.filter(status=finished)

    active_events = list(active_trees) + list(active_species)
    imports_finished = all(ie.is_finished() for ie in active_events)

    return {'active_trees': active_trees,
            'finished_trees': finished_trees,
            'active_species': active_species,
            'finished_species': finished_species,
            'imports_finished': imports_finished
            }


@login_required
@transaction.atomic
def merge_species(request, instance):
    # TODO: We don't set User.is_staff, probably should use a decorator anyways
    if not request.user.is_staff:
        raise Exception("Must be admin")

    species_to_delete_id = request.REQUEST['species_to_delete']
    species_to_replace_with_id = request.REQUEST['species_to_replace_with']

    species_to_delete = get_object_or_404(
        Species, instance=instance, pk=species_to_delete_id)
    species_to_replace_with = get_object_or_404(
        Species, instance=instance, pk=species_to_replace_with_id)

    if species_to_delete.pk == species_to_replace_with.pk:
        return HttpResponse(
            json.dumps({"error": "Must pick different species"}),
            content_type='application/json',
            status=400)

    # TODO: .update_with_user()?
    trees_to_update = Tree.objects\
        .filter(instance=instance)\
        .filter(species=species_to_delete)

    for tree in trees_to_update:
        tree.species = species_to_replace_with
        tree.save_with_system_user_bypass_auth()

    species_to_delete.delete_with_user(request.user)

    # Force a tree count update
    species_to_replace_with.tree_count = 0
    species_to_replace_with.save_with_user(User.system_user())

    return HttpResponse(
        json.dumps({"status": "ok"}),
        content_type='application/json')


def update_row(request, instance, import_type, row_id):
    """Update an importeventrow.

    Take the import_type and row_id from the URL and use it
    to retrieve the necessary row object. Then, iterate over
    the kvs in the json request body and set them on the row.
    """
    Clz = get_import_row_model(import_type)
    row = Clz.objects.get(pk=row_id)
    ie = row.import_event

    basedata = row.datadict

    for k, v in request.POST.iteritems():
        if k in basedata:
            basedata[k] = v

    # save the row and then perform validation, because
    # validation in this case is not the process of determining
    # if save is allowed, but rather of determining the error status
    # of the row and its fields so it can be presented correctly to
    # the user for further action.
    row.datadict = basedata
    row.save()
    row.validate_row()

    context = _get_status_panels(ie, instance)
    context['active_panel_name'] = 'error'
    return context


def show_import_status(request, instance, import_type, import_event_id):
    ie = _get_import_event(instance, import_type, import_event_id)

    if ie.status == GenericImportEvent.FAILED_FILE_VERIFICATION:
        template = 'importer/partials/file_status.html'
        ctx = {'ie': ie}
    else:
        template = 'importer/partials/row_status.html'
        ctx = _get_status_panels(ie, instance)

    return render_to_response(template, ctx, RequestContext(request))


def _get_status_panels(ie, instance):
    panels = [_get_status_panel(instance, ie, spec)
              for spec in _get_status_panel_specs(ie)]

    commit_url = reverse('importer:commit',
                         kwargs={'instance_url_name': instance.url_name,
                                 'import_type': ie.import_type,
                                 'import_event_id': ie.pk})
    return {
        'panels': panels,
        'active_panel_name': panels[0]['name'],
        'commit_url': commit_url
    }


def show_status_panel(request, instance, import_type, import_event_id):
    panel_name = request.GET.get('panel')
    page_number = int(request.GET.get('page'))

    ie = _get_import_event(instance, import_type, import_event_id)

    spec = [spec for spec in _get_status_panel_specs(ie)
            if spec['name'] == panel_name][0]

    panel = _get_status_panel(instance, ie, spec, page_number)

    return {
        'panel': panel
    }


def _get_import_event(instance, import_type, import_event_id):
    Model = get_import_event_model(import_type)
    return get_object_or_404(Model, pk=import_event_id, instance=instance)


def _get_status_panel(instance, ie, panel_spec, page_number=1):
    PAGE_SIZE = 10
    status = panel_spec['status']
    merge_required = panel_spec['name'] == 'merge_required'
    if merge_required:
        query = ie.rows() \
            .filter(merged=False) \
            .exclude(status=SpeciesImportRow.ERROR) \
            .order_by('idx')
    else:
        query = ie.rows() \
            .filter(status=status) \
            .order_by('idx')

    is_species = isinstance(ie, SpeciesImportEvent)
    if is_species and status == GenericImportRow.VERIFIED:
        query = query.filter(merged=True)

    field_names = [f.lower() for f
                   in json.loads(ie.field_order)
                   if f != 'ignore']

    class RowPage(Page):
        def __getitem__(self, *args, **kwargs):
            page = super(RowPage, self).__getitem__(*args, **kwargs)
            return _get_row_data(page,  field_names, merge_required)

    class RowPaginator(Paginator):
        def _get_page(self, *args, **kwargs):
            return RowPage(*args, **kwargs)

    row_pages = RowPaginator(query, PAGE_SIZE)
    row_page = row_pages.page(page_number)

    paging_url = reverse('importer:status_panel',
                         kwargs={'instance_url_name': instance.url_name,
                                 'import_type': ie.import_type,
                                 'import_event_id': ie.pk})
    paging_url += "?panel=%s" % panel_spec['name']

    return {
        'name': panel_spec['name'],
        'title': panel_spec['title'],
        'field_names': field_names,
        'row_count': row_pages.count,
        'rows': row_page,
        'paging_url': paging_url,
        'import_event_id': ie.pk,
        'import_type': ie.import_type
    }


def _add_species_resolver_to_fields(collected_fields, row):
    species_error_fields = ((f, v) for f, v in collected_fields.items()
                            if f in ('species', 'genus', 'cultivar')
                            and v.get('css_class'))

    for field, existing in species_error_fields:
        species_text = row.datadict.get('genus')
        if species_text:
            existing['custom_resolver']['is_species'] = True
            instance = row.import_event.instance
            suggesteds = _find_similar_species(species_text, instance)
            if suggesteds:
                existing['custom_resolver']['suggestion'] = suggesteds[0]


def _get_row_data(row, field_names, merge_required):
    """
    For each field with errors in each row, expand into an object
    for that field which presents rendering info about its most
    important (where fatal > warning) error.

    Merge this collection with some default information about fields
    that do not have any errors to produce complete rendering info
    for a row.
    """
    row_errors = row.errors_as_array()

    collected_fields = {}
    for row_error in row_errors:
        css_class = 'error' if row_error['fatal'] else 'warning'
        for field in row_error['fields']:
            field_data = collected_fields.get(field, {})
            if not field_data or css_class == 'error':
                field_data['name'] = field
                field_data['value'] = row.datadict[field]
                field_data['css_class'] = css_class
                if row_error['code'] != errors.MERGE_REQUIRED[0]:
                    field_data['show_resolver'] = True
                    field_data['msg'] = row_error['msg']
                    field_data['row_id'] = row.pk
                    field_data['custom_resolver'] = {}
            collected_fields[field] = field_data
    for field in field_names:
        if field not in collected_fields:
            collected_fields[field] = {'name': field,
                                       'value': row.datadict[field],
                                       'css_class': ''}

    if row.import_event.import_type == TreeImportEvent.import_type:
        _add_species_resolver_to_fields(collected_fields, row)

    fields = [collected_fields[f] for f in field_names]
    row_data = {'index': row.idx, 'fields': fields}

    if merge_required:
        merge_data = _get_merge_data(row, field_names, row_errors)
        row_data.update(merge_data)

    if hasattr(row, 'plot') and row.plot:
        row_data['plot_id'] = row.plot.pk

    if hasattr(row, 'species') and row.species:
        row_data['species_id'] = row.species.pk

    return row_data


def _get_merge_data(row, field_names, row_errors):
    error = [e for e in row_errors
             if e['code'] == errors.MERGE_REQUIRED[0]][0]
    species_diffs = error['data']
    diff_names = error['fields']

    # We know that genus/species/cultivar/other match.
    # Only allow creating a new species if "common name" doesn't match.
    create_species_allowed = 'common name' in diff_names

    # species_diffs is a list with one element per matching species.
    # Each element is a dict of fields where import and species differ:
    #    key: field_name
    #    value: [species_value, imported_value]
    #
    # Make a merge table whose rows contain:
    #    field_name | import_value | species_1_value | species_2_value ...

    def number_suffix(i):
        if len(species_diffs) > 1:
            return ' %s' % (i + 1)
        else:
            return ''

    columns_for_merge = [
        {
            'title': trans('Import Value'),
            'action_title': trans('Create New'),
            'species_id': 'new' if create_species_allowed else ''
        }
    ] + [
        {
            'title': trans('Match') + number_suffix(i),
            'action_title': trans('Merge with Match') + number_suffix(i),
            'species_id': diffs['id'][0]
        }
        for i, diffs in enumerate(species_diffs)
    ]

    merge_names = [name for name in field_names if name in diff_names]

    dom_names = ['row_%s_%s' % (row.idx, field_name.replace(' ', '_'))
                 for field_name in merge_names]

    # For the i-Tree code "imported value" display just region/code pairs which
    # differ from the species, rather than raw import value (which may
    # have region/code pairs which match the species)
    row_data = copy(row.datadict)
    f = fields.species
    for species_diff in species_diffs:
        if f.ITREE_CODE in species_diff:
            row_data[f.ITREE_CODE] = species_diff[f.ITREE_CODE][1]

    fields_to_merge = [
        {
            'name': field_name,
            'id': dom_name,
            'values': [
                _get_diff_value(dom_name, 0, row_data[field_name])
            ] + [
                _get_diff_value(dom_name, i + 1, diffs[field_name][0])
                for i, diffs in enumerate(species_diffs)
            ]
        }
        for (field_name, dom_name) in zip(merge_names, dom_names)]

    return {
        'columns_for_merge': columns_for_merge,
        'fields_to_merge': fields_to_merge,
        'merge_field_names': ','.join(merge_names),
        'radio_group_names': ','.join(dom_names),
        }


def _get_diff_value(dom_name, i, value):
    if not value:
        value = ''
    return {
        'id': "%s_%s" % (dom_name, i),
        'value': value,
        'checked': 'checked' if i == 0 else ''
    }


def _get_status_panel_specs(ie):
    verified_panel = {
        'name': 'verified',
        'status': GenericImportRow.VERIFIED,
        'title': trans('Ready to Add')
    }
    error_panel = {
        'name': 'error',
        'status': GenericImportRow.ERROR,
        'title': trans('Errors')
    }
    success_panel = {
        'name': 'success',
        'status': GenericImportRow.SUCCESS,
        'title': trans('Successfully Added')
    }

    if isinstance(ie, TreeImportEvent):
        warning_panel = {
            'name': 'warning',
            'status': TreeImportRow.WARNING,
            'title': trans('Warnings')
        }
        panels = [verified_panel, error_panel, warning_panel, success_panel]
    else:
        merge_required_panel = {
            'name': 'merge_required',
            'status': None,
            'title': trans('Merge Required')
        }
        panels = [
            verified_panel, merge_required_panel, error_panel, success_panel]
    return panels


# TODO: This is currently unused except for tests; likewise in OTM1.
# But it might be useful, e.g. to show in the UI why an import failed
def process_status(request, instance, import_type, import_event_id):
    ie = _get_import_event(instance, import_type, import_event_id)

    resp = None
    if ie.errors:
        resp = {'status': 'file_error',
                'errors': json.loads(ie.errors)}
    else:
        errors = []
        for row in ie.rows():
            if row.errors:
                errors.append((row.idx, json.loads(row.errors)))

        if len(errors) > 0:
            resp = {'status': 'row_error',
                    'errors': dict(errors)}

    if resp is None:
        resp = {'status': 'success',
                'rows': ie.rows().count()}

    return HttpResponse(json.dumps(resp), content_type='application/json')


def solve(request, instance, import_event_id, row_index):
    ie = get_object_or_404(SpeciesImportEvent, pk=import_event_id,
                           instance=instance)
    row = ie.rows().get(idx=row_index)

    data = dict(json.loads(request.REQUEST['data']))
    target_species = request.GET['species']

    # Strip off merge errors
    ierrors = [e for e in row.errors_as_array()
               if e['code'] != errors.MERGE_REQUIRED[0]]

    #TODO: Json handling is terrible.
    row.errors = json.dumps(ierrors)
    row.datadict.update(data)

    if target_species != 'new':
        row.species = get_object_or_404(Species, instance=instance,
                                        pk=target_species)

    row.merged = True
    row.save()

    row.validate_row()

    context = _get_status_panels(ie, instance)
    context['active_panel_name'] = 'merge_required'
    return context


@transaction.atomic
def commit(request, instance, import_type, import_event_id):
    ie = _get_import_event(instance, import_type, import_event_id)
    ie.status = GenericImportEvent.CREATING

    ie.save()
    ie.rows().update(status=GenericImportRow.WAITING)

    commit_import_event.delay(import_type, import_event_id)

    return list_imports(request, instance)


def process_csv(request, instance, import_type, **kwargs):
    files = request.FILES
    filename = files.keys()[0]
    file_obj = files[filename]

    file_obj = io.BytesIO(file_obj.read()
                          .decode('latin1')
                          .encode('utf-8'))

    owner = request.user
    ImportEventModel = get_import_event_model(import_type)
    ie = ImportEventModel(file_name=filename,
                          owner=owner,
                          instance=instance,
                          **kwargs)
    ie.save()

    run_import_event_validation.delay(import_type, ie.pk, file_obj)

    return ie.pk


all_species_fields = fields.species.ALL


def _build_species_object(species, fieldmap, included_fields):
    obj = {}

    for k, v in fieldmap.iteritems():
        if v in included_fields:
            val = getattr(species, k)
            if not val is None:
                if isinstance(val, unicode):
                    newval = val.encode("utf-8")
                else:
                    newval = str(val)
                obj[v] = newval.strip()

    return obj


@login_required
def export_all_species(request, instance):
    response = HttpResponse(mimetype='text/csv')

    # Maps [attr on species model] -> field name
    fieldmap = SpeciesImportRow.SPECIES_MAP

    include_extra_fields = request.GET.get('include_extra_fields', False)

    if include_extra_fields:
        extra_fields = (fields.species.ID,
                        fields.species.TREE_COUNT)
    else:
        extra_fields = tuple()

    included_fields = all_species_fields + extra_fields

    writer = csv.DictWriter(response, included_fields)
    writer.writeheader()

    for s in Species.objects.filter(instance=instance):
        obj = _build_species_object(s, fieldmap, included_fields)
        writer.writerow(obj)

    response['Content-Disposition'] = 'attachment; filename=species.csv'

    return response


@login_required
def export_single_species_import(request, instance, import_event_id):
    fieldmap = SpeciesImportRow.SPECIES_MAP

    ie = get_object_or_404(SpeciesImportEvent, instance=instance,
                           pk=import_event_id)

    response = HttpResponse(mimetype='text/csv')

    writer = csv.DictWriter(response, all_species_fields)
    writer.writeheader()

    for r in ie.rows():
        if r.species:
            obj = _build_species_object(r.species, fieldmap,
                                        all_species_fields)
        else:
            obj = lowerkeys(json.loads(r.data))

        writer.writerow(obj)

    response['Content-Disposition'] = 'attachment; filename=species.csv'

    return response


@login_required
def export_single_tree_import(request, instance, import_event_id):
    # TODO: Why doesn't this use fields.trees.ALL?
    all_fields = (
        fields.trees.POINT_X,
        fields.trees.POINT_Y,
        fields.trees.PLOT_WIDTH,
        fields.trees.PLOT_LENGTH,
        fields.trees.READ_ONLY,
        fields.trees.OPENTREEMAP_PLOT_ID,
        fields.trees.TREE_PRESENT,
        fields.trees.GENUS,
        fields.trees.SPECIES,
        fields.trees.CULTIVAR,
        fields.trees.OTHER_PART_OF_NAME,
        fields.trees.DIAMETER,
        fields.trees.TREE_HEIGHT,
        fields.trees.EXTERNAL_ID_NUMBER,
        fields.trees.CANOPY_HEIGHT,
        fields.trees.DATE_PLANTED,
    )

    ie = get_object_or_404(TreeImportEvent, instance=instance,
                           pk=import_event_id)

    response = HttpResponse(mimetype='text/csv')

    writer = csv.DictWriter(response, all_fields)
    writer.writeheader()

    for r in ie.rows():
        if r.plot:
            obj = {}
            obj[fields.trees.POINT_X] = r.plot.geometry.x
            obj[fields.trees.POINT_Y] = r.plot.geometry.y

            obj[fields.trees.PLOT_WIDTH] = r.plot.width
            obj[fields.trees.PLOT_LENGTH] = r.plot.length
            obj[fields.trees.READ_ONLY] = r.plot.readonly
            obj[fields.trees.OPENTREEMAP_PLOT_ID] = r.plot.pk
            obj[fields.trees.EXTERNAL_ID_NUMBER] = r.plot.owner_orig_id

            tree = r.plot.current_tree()

            obj[fields.trees.TREE_PRESENT] = tree is not None

            if tree:
                species = tree.species

                if species:
                    obj[fields.trees.GENUS] = species.genus
                    obj[fields.trees.SPECIES] = species.species
                    obj[fields.trees.CULTIVAR] = species.cultivar_name
                    obj[fields.trees.OTHER_PART_OF_NAME] =\
                        species.other_part_of_name

                obj[fields.trees.DIAMETER] = tree.dbh
                obj[fields.trees.TREE_HEIGHT] = tree.height
                obj[fields.trees.CANOPY_HEIGHT] = tree.canopy_height
                obj[fields.trees.DATE_PLANTED] = tree.date_planted

        else:
            obj = lowerkeys(json.loads(r.data))

        writer.writerow(obj)

    response['Content-Disposition'] = 'attachment; filename=trees.csv'

    return response


def _api_call(verb, view_fn):
    return do(
        admin_instance_request,
        requires_feature('bulk_upload'),
        require_http_method(verb),
        view_fn)


def _template_api_call(verb, template, view_fn):
    templated_view = render_template(template)(view_fn)
    return _api_call(verb, templated_view)


list_imports_endpoint = _template_api_call(
    'GET', 'importer/partials/imports.html', list_imports)

refresh_imports_endpoint = _template_api_call(
    'GET', 'importer/partials/import_tables.html', list_imports)

start_import_endpoint = _template_api_call(
    'POST', 'importer/partials/imports.html', start_import)

show_status_panel_endpoint = _template_api_call(
    'GET', 'importer/partials/status_table.html', show_status_panel)

solve_endpoint = _template_api_call(
    'POST', 'importer/partials/row_status.html', solve)

commit_endpoint = _template_api_call(
    'GET', 'importer/partials/imports.html', commit)

show_import_status_endpoint = _api_call('GET', show_import_status)

update_row_endpoint = _template_api_call(
    'POST', 'importer/partials/row_status.html', update_row)

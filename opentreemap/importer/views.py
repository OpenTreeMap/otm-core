# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import csv
import json
import io

from django.db import transaction
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from django.core.paginator import Paginator
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.translation import ugettext as trans

from django.contrib.auth.decorators import login_required

from opentreemap.util import decorate as do

from treemap.models import Species, Tree, User
from treemap.decorators import (admin_instance_request, require_http_method,
                                render_template, requires_feature)

from importer.models import GenericImportEvent, GenericImportRow
from importer.trees import TreeImportEvent, TreeImportRow
from importer.species import SpeciesImportEvent, SpeciesImportRow
from importer.tasks import (run_import_event_validation, commit_import_event,
                            get_import_event_model)
from importer import errors, fields


def clean_string(s):
    s = s.strip()
    if not isinstance(s, unicode):
        s = unicode(s, 'utf-8')
    return s


def lowerkeys(h):
    h2 = {}
    for (k, v) in h.iteritems():
        k = k.lower().strip()
        if k != 'ignore':
            if isinstance(v, basestring):
                v = clean_string(v)

            h2[k] = v

    return h2


def find_similar_species(request, instance):
    target = request.REQUEST['target']

    species = Species.objects\
                     .filter(instance=instance)\
                     .extra(
                         select={
                             'l': ("levenshtein(genus || ' ' || species || "
                                   "' ' || cultivar_name || ' ' || "
                                   "other_part_of_name, %s)")
                         },
                         select_params=(target,))\
                     .order_by('l')[0:2]  # Take top 2

    output = [{fields.trees.GENUS: s.genus,
               fields.trees.SPECIES: s.species,
               fields.trees.CULTIVAR: s.cultivar_name,
               fields.trees.OTHER_PART_OF_NAME: s.other_part_of_name,
               'pk': s.pk} for s in species]

    return HttpResponse(json.dumps(output), content_type='application/json')


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
            float(request.REQUEST.get('unit_diameterh', 1.0)),

            'tree_height_conversion_factor':
            float(request.REQUEST.get('unit_tree_height', 1.0)),

            'canopy_height_conversion_factor':
            float(request.REQUEST.get('unit_canopy_height', 1.0))
        }
    else:
        kwargs = {}

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


@login_required
def update(request, instance, import_type, import_event_id):
    ie = _get_import_event(instance, import_type, import_event_id)

    rowdata = json.loads(request.REQUEST['row'])
    idx = rowdata['id']

    row = ie.rows().get(idx=idx)
    basedata = row.datadict

    for k, v in rowdata.iteritems():
        if k in basedata:
            basedata[k] = v

    # TODO: Validate happens *after* save()?
    row.datadict = basedata
    row.save()
    row.validate_row()

    return HttpResponse()


# TODO: Remove this method
@login_required
def update_row(request, instance, import_event_row_id):
    update_keys = {key.split('update__')[1]
                   for key
                   in request.REQUEST.keys()
                   if key.startswith('update__')}

    row = TreeImportRow.objects.get(pk=import_event_row_id)

    basedata = row.datadict

    for key in update_keys:
        basedata[key] = request.REQUEST['update__%s' % key]

    row.datadict = basedata
    row.save()
    row.validate_row()

    return HttpResponseRedirect(reverse('importer:show_import_status',
                                        args=(row.import_event.pk,)))


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

    row_data = [_get_row_data(row, field_names, merge_required)
                for row in query]
    rows = Paginator(row_data, PAGE_SIZE).page(page_number)

    paging_url = reverse('importer:status_panel',
                         kwargs={'instance_url_name': instance.url_name,
                                 'import_type': ie.import_type,
                                 'import_event_id': ie.pk})
    paging_url += "?panel=%s" % panel_spec['name']

    return {
        'name': panel_spec['name'],
        'title': panel_spec['title'],
        'field_names': field_names,
        'row_count': len(row_data),
        'rows': rows,
        'paging_url': paging_url,
        'import_event_id': ie.pk
    }


def _get_row_data(row, field_names, merge_required):
    row_errors = row.errors_as_array()
    error_fields = [e['fields'] for e in row_errors if e['fatal']]
    error_fields = set(sum(error_fields, []))
    warning_fields = [e['fields'] for e in row_errors if not e['fatal']]
    warning_fields = set(sum(warning_fields, []))

    field_data = [
        _get_field_data(row, field_name, error_fields, warning_fields)
        for field_name in field_names]

    row_data = {
        'index': row.idx,
        'fields': field_data
    }

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
            'action_title': trans('Create New Species'),
            'species_id': 'new' if create_species_allowed else ''
        }
    ] + [
        {
            'title': trans('Species Match') + number_suffix(i),
            'action_title': trans('Update Species') + number_suffix(i),
            'species_id': diffs['id'][0]
        }
        for i, diffs in enumerate(species_diffs)
    ]

    merge_names = [name for name in field_names if name in diff_names]

    dom_names = ['row_%s_%s' % (row.idx, field_name.replace(' ', '_'))
                 for field_name in merge_names]

    fields_to_merge = [
        {
            'name': field_name,
            'id': dom_name,
            'values': [
                _get_diff_value(dom_name, 0, row.datadict[field_name])
            ] + [
                _get_diff_value(dom_name, i + 1, diffs.get(field_name))
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
    if isinstance(value, list):
        value = value[0]
    elif not value:
        value = ''
    return {
        'id': "%s_%s" % (dom_name, i),
        'value': value,
        'checked': 'checked' if i == 0 else ''
    }


def _get_field_data(row, field_name, error_fields, warning_fields):
    if field_name in error_fields:
        css_class = 'error'
    elif field_name in warning_fields:
        css_class = 'warning'
    else:
        css_class = ''
    return {
        'name': field_name,
        'value': row.datadict[field_name],
        'css_class': css_class
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

    try:
        rows = create_rows_for_event(ie, file_obj)
        if rows:
            run_import_event_validation.delay(import_type, ie.pk)
    except Exception as e:
        ie.append_error(errors.GENERIC_ERROR, data=[str(e)])
        ie.status = GenericImportEvent.FAILED_FILE_VERIFICATION
        ie.save()

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


@transaction.atomic
def create_rows_for_event(ie, csvfile):
    rows = []
    reader = csv.DictReader(csvfile)

    fieldnames = reader.fieldnames
    ie.field_order = json.dumps(fieldnames)
    ie.save()

    idx = 0
    for row in reader:
        # TODO: should we even create a row if
        # we're about to break out? It's not like
        # the file errors get attached to the row
        # anyway.
        rows.append(
            ie.create_row(
                data=json.dumps(lowerkeys(row)),
                import_event=ie, idx=idx))

        # perform file validation with first row
        if idx == 0:
            # Break out early if there was an error
            # with the basic file structure
            ie.validate_main_file()
            if ie.has_errors():
                break
        idx += 1
    else:
        ie.validate_main_file()

    return False if ie.has_errors() else rows


def _api_call(verb, template, view_fn):
    return do(
        admin_instance_request,
        requires_feature('bulk_upload'),
        require_http_method(verb),
        render_template(template),
        view_fn)


list_imports_endpoint = _api_call(
    'GET', 'importer/partials/imports.html', list_imports)

refresh_imports_endpoint = _api_call(
    'GET', 'importer/partials/import_tables.html', list_imports)

start_import_endpoint = _api_call(
    'POST', 'importer/partials/imports.html', start_import)

show_status_panel_endpoint = _api_call(
    'GET', 'importer/partials/status_table.html', show_status_panel)

solve_endpoint = _api_call(
    'POST', 'importer/partials/status.html', solve)

commit_endpoint = _api_call(
    'GET', 'importer/partials/imports.html', commit)

show_import_status_endpoint = do(
    admin_instance_request,
    requires_feature('bulk_upload'),
    require_http_method('GET'),
    show_import_status)

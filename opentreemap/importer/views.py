# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
import io
import csv

from copy import copy
from celery.result import GroupResult, AsyncResult

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.core.paginator import Paginator, Page, EmptyPage
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils.translation import ugettext as _

from treemap.models import Species, Tree, User, MapFeature
from treemap.units import (storage_to_instance_units_factor,
                           get_value_display_attr)
from treemap.plugin import get_tree_limit

from exporter.decorators import task_output_as_csv, queryset_as_exported_csv

from importer.models.base import GenericImportEvent, GenericImportRow
from importer.models.trees import TreeImportEvent, TreeImportRow
from importer.models.species import SpeciesImportEvent, SpeciesImportRow
from importer.tasks import (run_import_event_validation, commit_import_event,
                            get_import_event_model, get_import_row_model,
                            get_import_export)
from importer import errors, fields

TABLE_ACTIVE_TREES = 'activeTrees'
TABLE_FINISHED_TREES = 'finishedTrees'
TABLE_ACTIVE_SPECIES = 'activeSpecies'
TABLE_FINISHED_SPECIES = 'finishedSpecies'


def _find_similar_species(target, instance):
    search_exp = " || ".join(["genus", "' '", "species", "' '",
                              "cultivar", "' '", "other_part_of_name"])
    lev_exp = "levenshtein(%s, %%s)" % search_exp
    species = (Species.objects
               .filter(instance=instance)
               .extra(select={'l': lev_exp}, select_params=(target,))
               .order_by('l')[0:2])  # Take top 2

    output = [{fields.trees.GENUS: s.genus,
               fields.trees.SPECIES: s.species,
               fields.trees.CULTIVAR: s.cultivar,
               fields.trees.OTHER_PART_OF_NAME: s.other_part_of_name,
               'display_name': s.display_name,
               'pk': s.pk} for s in species]

    return output


def start_import(request, instance):
    if not getattr(request, 'FILES'):
        return HttpResponseBadRequest("No attachment received")

    import_type = request.POST['type']
    if import_type == TreeImportEvent.import_type:
        table = TABLE_ACTIVE_TREES
        factors = {
            'diameter_conversion_factor': ('tree', 'diameter'),
            'tree_height_conversion_factor': ('tree', 'height'),
            'canopy_height_conversion_factor': ('tree', 'canopy_height'),
            'plot_length_conversion_factor': ('plot', 'length'),
            'plot_width_conversion_factor': ('plot', 'width'),
        }
    else:
        table = TABLE_ACTIVE_SPECIES
        factors = {
            'max_diameter_conversion_factor': ('tree', 'diameter'),
            'max_tree_height_conversion_factor': ('tree', 'height'),
        }

    kwargs = {k: 1 / storage_to_instance_units_factor(instance, v[0], v[1])
              for (k, v) in factors.items()}

    process_csv(request, instance, import_type, **kwargs)

    return get_import_table(request, instance, table)


def list_imports(request, instance):
    table_names = [TABLE_ACTIVE_TREES, TABLE_FINISHED_TREES,
                   TABLE_ACTIVE_SPECIES, TABLE_FINISHED_SPECIES]

    _cleanup_tables(instance)
    tables = [_get_table_context(instance, table_name, 1)
              for table_name in table_names]

    instance_units = {k + '_' + v:
                          get_value_display_attr(instance, k, v, 'units')[1]
                      for k, v in [('plot', 'width'),
                                   ('plot', 'length'),
                                   ('tree', 'height'),
                                   ('tree', 'diameter'),
                                   ('tree', 'canopy_height')]}
    return {
        'tables': tables,
        'importer_instance_units': instance_units,
    }


def get_import_table(request, instance, table_name):
    page_number = int(request.GET.get('page', '1'))
    _cleanup_tables(instance)
    return {
        'table': _get_table_context(instance, table_name, page_number)
    }


_EVENT_TABLE_PAGE_SIZE = 5


def _cleanup_tables(instance):
    q = Q(instance=instance, is_lost=False)
    ievents = (list(TreeImportEvent.objects.filter(q)) +
               list(SpeciesImportEvent.objects.filter(q)))

    for ie in ievents:
        mark_lost = False
        if ie.has_not_been_processed_recently():
            mark_lost = True
        elif ie.task_id != '' and ie.is_running():
            result = AsyncResult(ie.task_id)
            if not result or result.failed():
                mark_lost = True

        if mark_lost:
            ie.is_lost = True
            ie.mark_finished_and_save()


def _get_table_context(instance, table_name, page_number):
    trees = TreeImportEvent.objects \
        .filter(instance=instance) \
        .order_by('-created')
    species = SpeciesImportEvent.objects \
        .filter(instance=instance) \
        .order_by('-created')
    inactive_q = Q(is_lost=True) | Q(
        status__in={
            GenericImportEvent.FINISHED_CREATING,
            GenericImportEvent.FAILED_FILE_VERIFICATION})
    trees_inactive_q = inactive_q | ~Q(
        schema_version=TreeImportEvent.import_schema_version)
    species_inactive_q = inactive_q | ~Q(
        schema_version=SpeciesImportEvent.import_schema_version)

    if table_name == TABLE_ACTIVE_TREES:
        title = _('Active Tree Imports')
        rows = trees.exclude(trees_inactive_q)

    elif table_name == TABLE_FINISHED_TREES:
        title = _('Finished Tree Imports')
        rows = trees.filter(trees_inactive_q)

    elif table_name == TABLE_ACTIVE_SPECIES:
        title = _('Active Species Imports')
        rows = species.exclude(species_inactive_q)

    elif table_name == TABLE_FINISHED_SPECIES:
        title = _('Finished Species Imports')
        rows = species.filter(species_inactive_q)

    else:
        raise Exception('Unexpected import table name: %s' % table_name)

    # Get has_pending before filtering by page so that completing an
    # import on a non-visible page will still trigger a refresh of the
    # finished table
    has_pending = any(not ie.is_finished() for ie in rows)

    paginator = Paginator(rows, _EVENT_TABLE_PAGE_SIZE)
    rows = paginator.page(min(page_number, paginator.num_pages))

    paging_url = reverse('importer:get_import_table',
                         args=(instance.url_name, table_name))
    refresh_url = paging_url + '?page=%s' % page_number

    return {
        'name': table_name,
        'title': title,
        'page_size': _EVENT_TABLE_PAGE_SIZE,
        'rows': rows,
        'has_pending': has_pending,
        'paging_url': paging_url,
        'refresh_url': refresh_url,
    }


@transaction.atomic
def merge_species(request, instance):
    species_to_delete_id = request.POST['species_to_delete']
    species_to_replace_with_id = request.POST['species_to_replace_with']

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
    trees_to_update = Tree.objects \
        .filter(instance=instance) \
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

    # Minor workaround for updating species columns in tree imports
    # The client sends up a species_id field, which does not match any of the
    # columns in the ImportRow. If it is present, we look up the species in the
    # DB and fill in the appropriate species fields in the ImportRow
    if 'species_id' in request.POST:
        # this round tripped from the server, so it should always have a match.
        species = Species.objects.get(pk=request.POST['species_id'])
        basedata.update({
            fields.trees.GENUS: species.genus,
            fields.trees.SPECIES: species.species,
            fields.trees.CULTIVAR: species.cultivar,
            fields.trees.OTHER_PART_OF_NAME: species.other_part_of_name,
            fields.trees.COMMON_NAME: species.common_name
        })

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

    panel_name = request.GET.get('panel', 'verified')
    page_number = int(request.GET.get('page', '1'))
    context = _get_status_panels(ie, instance, panel_name, page_number)
    return context


def show_import_status(request, instance, import_type, import_event_id):
    ie = _get_import_event(instance, import_type, import_event_id)

    if ie.status == GenericImportEvent.FAILED_FILE_VERIFICATION:
        template = 'importer/partials/file_status.html'
        legal_fields, required_fields = \
            ie.legal_and_required_fields_title_case()
        ctx = {'ie': ie,
               'legal_fields': sorted(legal_fields),
               'required_fields': sorted(required_fields),
               'is_missing_field': ie.has_error(errors.MISSING_FIELD),
               'has_unmatched_field': ie.has_error(errors.UNMATCHED_FIELDS)}
    else:
        template = 'importer/partials/row_status.html'
        panel_name = request.GET.get('panel', 'verified')
        page_number = int(request.GET.get('page', '1'))

        ctx = _get_status_panels(ie, instance, panel_name, page_number)

    return render(request, template, context=ctx)


def _get_tree_limit_context(ie):
    if ie.import_type == 'species':
        return {}

    tree_limit = get_tree_limit(ie.instance)

    if tree_limit is None:
        return {}

    tree_count = MapFeature.objects.filter(instance=ie.instance).count()
    remaining_tree_limit = tree_limit - tree_count

    plot_id_absent_q = \
        Q(data__contains='"planting site id": ""') | \
        ~Q(data__contains='"planting site id"')
    tree_id_absent_q = \
        Q(data__contains='"tree id": ""') | \
        ~Q(data__contains='"tree id"')
    verified_added_q = \
        Q(status=TreeImportRow.VERIFIED) & plot_id_absent_q & tree_id_absent_q

    verified_count = ie.rows()\
        .filter(verified_added_q)\
        .count()

    tree_limit_exceeded = remaining_tree_limit - verified_count < 0

    return {
        'tree_limit': tree_limit,
        'tree_count': tree_count,
        'remaining_tree_limit': remaining_tree_limit,
        'tree_limit_exceeded': tree_limit_exceeded,
    }


def _get_status_panels(ie, instance, panel_name, page_number):
    get_page = lambda spec_name: page_number if spec_name == panel_name else 1

    panels = [_get_status_panel(instance, ie, spec, get_page(spec['name']))
              for spec in _get_status_panel_specs(ie)]

    commit_url = reverse('importer:commit',
                         kwargs={'instance_url_name': instance.url_name,
                                 'import_type': ie.import_type,
                                 'import_event_id': ie.pk})

    cancel_url = reverse('importer:cancel',
                         kwargs={'instance_url_name': instance.url_name,
                                 'import_type': ie.import_type,
                                 'import_event_id': ie.pk})

    ctx = {
        'panels': panels,
        'active_panel_name': panel_name,
        'commit_url': commit_url,
        'cancel_url': cancel_url,
        'ie': ie,
    }

    ctx.update(_get_tree_limit_context(ie))
    return ctx


def _get_import_event(instance, import_type, import_event_id):
    Model = get_import_event_model(import_type)
    return get_object_or_404(Model, pk=import_event_id, instance=instance)


def _get_status_panel(instance, ie, panel_spec, page_number=1):
    PAGE_SIZE = 10
    status = panel_spec['status']
    merge_required = panel_spec['name'] == 'merge_required'
    show_warnings = panel_spec['name'] != 'success'

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

    field_names_original = [f.strip() for f in json.loads(ie.field_order)
                            if f != 'ignore']
    field_names = [f.lower() for f in field_names_original]

    class RowPage(Page):
        def __getitem__(self, *args, **kwargs):
            row = super(RowPage, self).__getitem__(*args, **kwargs)
            return _get_row_data(
                row, field_names, merge_required, show_warnings)

    class RowPaginator(Paginator):
        def _get_page(self, *args, **kwargs):
            return RowPage(*args, **kwargs)

    row_pages = RowPaginator(query, PAGE_SIZE)

    try:
        row_page = row_pages.page(page_number)
    except EmptyPage:
        # If the page number is out of bounds, return the last page
        row_page = row_pages.page(row_pages.num_pages)

    paging_url = reverse('importer:status',
                         kwargs={'instance_url_name': instance.url_name,
                                 'import_type': ie.import_type,
                                 'import_event_id': ie.pk})
    panel_query = "?panel=%s" % panel_spec['name']
    paging_url += panel_query
    panel_and_page = panel_query + "&page=%s" % page_number

    return {
        'name': panel_spec['name'],
        'title': panel_spec['title'],
        'field_names': field_names_original,
        'row_count': row_pages.count,
        'rows': row_page,
        'paging_url': paging_url,
        'import_event_id': ie.pk,
        'import_type': ie.import_type,
        'panel_and_page': panel_and_page
    }


def _add_species_resolver_to_fields(collected_fields, row):
    species_error_fields = ((f, v) for f, v in collected_fields.items()
                            if f in fields.trees.SPECIES_FIELDS
                            and v.get('css_class'))

    for field, existing in species_error_fields:
        species_text = row.datadict.get('genus')
        if species_text:
            existing['custom_resolver']['is_species'] = True
            instance = row.import_event.instance
            suggesteds = _find_similar_species(species_text, instance)
            if suggesteds:
                existing['custom_resolver']['suggestion'] = suggesteds[0]


def _get_row_data(row, field_names, merge_required, show_warnings):
    """
    For each field with errors in each row, expand into an object
    for that field which presents rendering info about its most
    important (where fatal > warning) error.

    Merge this collection with some default information about fields
    that do not have any errors to produce complete rendering info
    for a row.
    """
    row_errors = row.errors_array_with_messages()

    collected_fields = {}
    for row_error in row_errors:
        if row_error['fatal']:
            css_class = 'error'
        elif show_warnings:
            css_class = 'warning'
        else:
            css_class = None
        if css_class:
            for field in row_error['fields']:
                field_data = collected_fields.get(field, {})
                if not field_data or css_class == 'error':
                    field_data['name'] = field
                    field_data['value'] = row.datadict.get(field, '')
                    field_data['css_class'] = css_class
                    if row_error['code'] != errors.MERGE_REQUIRED[0]:
                        field_data['show_resolver'] = True
                        field_data['msg'] = row_error['msg']
                        field_data['row_id'] = row.pk
                        field_data['custom_resolver'] = {}
                        field_data['help_text'] = _get_help_text(row_error)
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


def _get_help_text(row_error):
    help_text = None
    if errors.is_itree_error_code(row_error['code']):
        help_text = _('Please consult the OpenTreeMap Species Import '
                      'Guide for information on resolving this error.')
    return help_text


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
            'title': _('Import Value'),
            'action_title': _('Create New'),
            'species_id': 'new' if create_species_allowed else ''
        }
    ] + [
        {
            'title': _('Match') + number_suffix(i),
            'action_title': _('Merge with Match') + number_suffix(i),
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
                _get_diff_value(dom_name, i + 1,
                                diffs.get(field_name, [''])[0])
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
        'title': _('Ready to Add')
    }
    error_panel = {
        'name': 'error',
        'status': GenericImportRow.ERROR,
        'title': _('Errors')
    }
    success_panel = {
        'name': 'success',
        'status': GenericImportRow.SUCCESS,
        'title': _('Successfully Added')
    }

    if isinstance(ie, TreeImportEvent):
        warning_panel = {
            'name': 'warning',
            'status': TreeImportRow.WARNING,
            'title': _('Warnings')
        }
        panels = [verified_panel, error_panel, warning_panel, success_panel]
    else:
        merge_required_panel = {
            'name': 'merge_required',
            'status': None,
            'title': _('Merge Required')
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

    data = dict(json.loads(request.POST['data']))
    target_species = request.GET['species']

    # Strip off merge errors
    # TODO: Json handling is terrible.
    row.errors = json.dumps(row.errors_array_without_merge_errors())
    row.datadict.update(data)
    row.datadict = row.datadict  # invoke setter to update row.data

    if target_species != 'new':
        row.species = get_object_or_404(Species, instance=instance,
                                        pk=target_species)

    row.merged = True
    row.save()

    row.validate_row()

    context = _get_status_panels(ie, instance, 'merge_required', 1)
    return context


def commit(request, instance, import_type, import_event_id):
    with transaction.atomic():
        ie = _get_import_event(instance, import_type, import_event_id)

        if _get_tree_limit_context(ie).get('tree_limit_exceeded'):
            raise Exception(_("tree limit exceeded"))

        ie.status = GenericImportEvent.CREATING

        ie.update_progress_timestamp_and_save()
        ie.rows().update(status=GenericImportRow.WAITING)

    commit_import_event.delay(import_type, import_event_id)

    return list_imports(request, instance)


def process_csv(request, instance, import_type, **kwargs):
    files = request.FILES
    filename = files.keys()[0]
    file_obj = files[filename]

    file_obj = io.BytesIO(decode(file_obj.read()).encode('utf-8'))

    owner = request.user
    ImportEventModel = get_import_event_model(import_type)
    ie = ImportEventModel(file_name=filename,
                          owner=owner,
                          instance=instance,
                          **kwargs)
    ie.save()

    run_import_event_validation.delay(import_type, ie.pk, file_obj)

    return ie.pk


# http://stackoverflow.com/a/8898439/362702
def decode(s):
    for encoding in "utf-8-sig", "utf-16":
        try:
            return s.decode(encoding)
        except UnicodeDecodeError:
            continue
    return s.decode("latin-1")


@transaction.atomic
def cancel(request, instance, import_type, import_event_id):
    ie = _get_import_event(instance, import_type, import_event_id)

    ie.status = GenericImportEvent.CANCELED
    ie.mark_finished_and_save()

    # If verifications tasks are still scheduled, we need to revoke them
    if ie.task_id:
        result = GroupResult.restore(ie.task_id)
        if result:
            result.revoke()

    # If we couldn't get the task, it is already effectively cancelled

    return list_imports(request, instance)


@queryset_as_exported_csv
def export_all_species(request, instance):
    field_names = SpeciesImportRow.SPECIES_MAP.keys()
    field_names.remove('id')
    return Species.objects.filter(instance_id=instance.id).values(*field_names)


@task_output_as_csv
def export_single_import(request, instance, import_type, import_event_id):
    ie = _get_import_event(instance, import_type, import_event_id)

    if import_type == SpeciesImportEvent.import_type:
        filename = "species.csv"
        field_names = fields.species.ALL
    else:
        filename = "trees.csv"
        field_names = ie.ordered_legal_fields()  # TODO: use ie's saved fields

    return filename, get_import_export, (import_type, ie.pk,), field_names


def download_import_template(request, instance, import_type):
    if import_type == SpeciesImportEvent.import_type:
        filename = 'OpenTreeMap_Species_Import_Template.csv'
        field_names = fields.title_case(fields.species.ALL)
    else:
        filename = 'OpenTreeMap_Tree_Import_Template.csv'
        ie = TreeImportEvent(instance=instance)
        field_names = ie.ordered_legal_fields_title_case()

    # Encoding the field names prevents an error when the field names have
    # non-ASCII characters.
    field_names = [field_name.encode('utf-8') for field_name in field_names]

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=%s" % filename
    writer = csv.DictWriter(response, field_names)
    writer.writeheader()

    return response

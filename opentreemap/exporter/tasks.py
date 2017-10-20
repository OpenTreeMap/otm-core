# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import csv
import logging

from contextlib import contextmanager
from functools import wraps
from collections import OrderedDict
from celery import shared_task
from tempfile import TemporaryFile

from django.core.files import File

from treemap.search import Filter
from treemap.models import Species, Plot
from treemap.util import safe_get_model_class
from treemap.audit import model_hasattr
from treemap.udf import UserDefinedCollectionValue
from treemap.units import (storage_to_instance_units_factor,
                           get_value_display_attr)

from treemap.lib.object_caches import udf_defs

from djqscsv import write_csv, generate_filename

from opentreemap.util import add_rollbar_handler

from exporter.models import ExportJob
from exporter.user import write_users
from exporter.util import sanitize_unicode_record

from importer import fields


logger = logging.getLogger(__name__)
add_rollbar_handler(logger, level=logging.INFO)


@contextmanager
def _job_transaction_manager(job_pk):
    job = ExportJob.objects.get(pk=job_pk)
    try:
        yield job
    except:
        job.fail()
        job.save()
        raise


def _job_transaction(fn):
    @wraps(fn)
    def wrapper(job_pk, *args, **kwargs):
        with _job_transaction_manager(job_pk) as job:
            return fn(job, *args, **kwargs)
    return wrapper


def _values_for_model(
        instance, job, table, model,
        select, select_params, prefix=None):
    if prefix:
        prefix += '__'
    else:
        prefix = ''

    prefixed_names = []
    model_class = safe_get_model_class(model)
    dummy_instance = model_class()

    if hasattr(model_class, 'instance'):
        dummy_instance.instance = instance

    for field_name in dummy_instance.visible_fields(job.user):
        prefixed_name = prefix + field_name

        if field_name.startswith('udf:'):
            name = field_name[4:]
            if name in model_class.collection_udf_settings.keys():
                field_definition_id = None
                for udfd in udf_defs(instance, model):
                    if udfd.iscollection and udfd.name == name:
                        field_definition_id = udfd.id

                if field_definition_id is None:
                    continue

                select[prefixed_name] = (
                    """
                    WITH formatted_data AS (
                        SELECT concat('(', data, ')') as fdata
                        FROM %s
                        WHERE field_definition_id = %s and model_id = %s.id
                    )

                    SELECT array_to_string(array_agg(fdata), ', ', '*')
                    FROM formatted_data
                    """
                    % (UserDefinedCollectionValue._meta.db_table,
                       field_definition_id, table))
            else:
                select[prefixed_name] = "{0}.udfs->%s".format(table)
                select_params.append(name)
        else:
            if not model_hasattr(dummy_instance, field_name):
                # Exception will be raised downstream if you look for
                # a field on a model that no longer exists but still
                # has a stale permission record. Here we check for that
                # case and don't include the field if it does not exist.
                continue

        prefixed_names.append(prefixed_name)

    return prefixed_names


@shared_task
@_job_transaction
def async_users_export(job, data_format):
    instance = job.instance

    if data_format == 'csv':
        filename = 'users.csv'
    else:
        filename = 'users.json'

    file_obj = TemporaryFile()
    write_users(data_format, file_obj, instance)
    job.complete_with(filename, File(file_obj))
    job.save()


@shared_task
@_job_transaction
def async_csv_export(job, model, query, display_filters):
    instance = job.instance

    select = OrderedDict()
    select_params = []
    field_header_map = {}
    field_serializer_map = {}
    if model == 'species':
        initial_qs = (Species.objects.
                      filter(instance=instance))
        values = _values_for_model(instance, job, 'treemap_species',
                                   'Species', select, select_params)
        field_names = values + select.keys()
        limited_qs = (initial_qs
                      .extra(select=select,
                             select_params=select_params)
                      .values(*field_names))
    else:
        # model == 'tree'

        # TODO: if an anonymous job with the given query has been
        # done since the last update to the audit records table,
        # just return that job

        # get the plots for the provided
        # query and turn them into a tree queryset
        initial_qs = Filter(query, display_filters, instance)\
            .get_objects(Plot)

        tree_fields = _values_for_model(
            instance, job, 'treemap_tree', 'Tree',
            select, select_params,
            prefix='tree')
        plot_fields = _values_for_model(
            instance, job, 'treemap_mapfeature', 'Plot',
            select, select_params)
        species_fields = _values_for_model(
            instance, job, 'treemap_species', 'Species',
            select, select_params,
            prefix='tree__species')

        if 'geom' in plot_fields:
            plot_fields = [f for f in plot_fields if f != 'geom']
            plot_fields += ['geom__x', 'geom__y']

        if tree_fields:
            select['tree_present'] = "treemap_tree.id is not null"
            plot_fields += ['tree_present']

        get_ll = 'ST_Transform(treemap_mapfeature.the_geom_webmercator, 4326)'
        select['geom__x'] = 'ST_X(%s)' % get_ll
        select['geom__y'] = 'ST_Y(%s)' % get_ll

        plot_fields += ['updated_by__username']

        field_names = set(tree_fields + plot_fields + species_fields)

        if field_names:
            field_header_map = _csv_field_header_map(field_names)
            field_serializer_map = _csv_field_serializer_map(instance,
                                                             field_names)
            limited_qs = (initial_qs
                          .extra(select=select,
                                 select_params=select_params)
                          .values(*field_header_map.keys()))
        else:
            limited_qs = initial_qs.none()

    if not initial_qs.exists():
        job.status = ExportJob.EMPTY_QUERYSET_ERROR

    # if the initial queryset was not empty but the limited queryset
    # is empty, it means that there were no fields which the user
    # was allowed to export.
    elif not limited_qs.exists():
        job.status = ExportJob.MODEL_PERMISSION_ERROR
    else:
        csv_file = TemporaryFile()
        write_csv(limited_qs, csv_file,
                  field_order=field_header_map.keys(),
                  field_header_map=field_header_map,
                  field_serializer_map=field_serializer_map)
        filename = generate_filename(limited_qs).replace('plot', 'tree')
        job.complete_with(filename, File(csv_file))

    job.save()


def _csv_field_header_map(field_names):
    map = OrderedDict()
    # TODO: make this conditional based on whether or not
    # we are performing a complete export or an "importable" export
    omit = {'feature_type',
            'hide_at_zoom',
            'instance',
            'mapfeature_ptr',
            'readonly',
            'udfs',
            'updated_by',
            'tree__instance',
            'tree__plot',
            'tree__readonly',
            'tree__species',
            'tree__species__fact_sheet_url',
            'tree__species__fall_conspicuous',
            'tree__species__flower_conspicuous',
            'tree__species__flowering_period',
            'tree__species__fruit_or_nut_period',
            'tree__species__has_wildlife_value',
            'tree__species__id',
            'tree__species__instance',
            'tree__species__is_native',
            'tree__species__max_diameter',
            'tree__species__max_height',
            'tree__species__otm_code',
            'tree__species__palatable_human',
            'tree__species__plant_guide_url',
            'tree__species__udfs',
            'tree__species__updated_at',
            'tree__udfs'}

    field_names = field_names - omit

    for name, header in fields.trees.EXPORTER_PAIRS:
        if name in field_names:
            map[name] = header.title()
            field_names.remove(name)

    for name in sorted(field_names):
        if name.startswith('udf:'):
            header = 'Planting Site: ' + name[4:]
        elif name.startswith('tree__udf:'):
            header = 'Tree: ' + name[10:]
        else:
            logger.warn('Unrecognized export field name',
                        extra={'extra_data': {'field_name': name}})
            continue
        map[name] = header
    return map


def _csv_field_serializer_map(instance, field_names):
    """
    Create serializer functions that convert values to the proper units.
    """
    map = {}
    convertable_fields = {'tree__diameter': ('tree', 'diameter'),
                          'tree__height': ('tree', 'height'),
                          'tree__canopy_height': ('tree', 'canopy_height'),
                          'width': ('plot', 'width'),
                          'length': ('plot', 'length')}

    def make_serializer(factor, digits):
        return lambda x: str(round(factor * x, digits))

    for name, details in convertable_fields.iteritems():
        model_name, field = details
        factor = storage_to_instance_units_factor(instance,
                                                  model_name,
                                                  field)
        _, digits = get_value_display_attr(instance, model_name, field,
                                           'digits')
        digits = int(digits)
        map[name] = make_serializer(factor, digits)
    return map


@shared_task
@_job_transaction
def simple_async_csv(job, qs):
    file_obj = TemporaryFile()
    write_csv(qs, file_obj)
    job.complete_with(generate_filename(qs), File(file_obj))
    job.save()


@shared_task
def custom_async_csv(csv_rows, job_pk, filename, fields):
    with _job_transaction_manager(job_pk) as job:
        csv_obj = TemporaryFile()

        writer = csv.DictWriter(csv_obj, fields)
        writer.writeheader()
        for row in csv_rows:
            writer.writerow(sanitize_unicode_record(row))

        job.complete_with(filename, File(csv_obj))
        job.save()

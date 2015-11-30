# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import csv

from contextlib import contextmanager
from functools import wraps
from collections import OrderedDict
from celery import task
from tempfile import TemporaryFile

from django.core.files import File

from treemap.search import Filter
from treemap.models import Species, Plot
from treemap.util import safe_get_model_class
from treemap.audit import model_hasattr, FieldPermission
from treemap.ecobenefits import TreeBenefitsCalculator, BenefitCategory
from treemap.lib.object_caches import udf_defs, permissions
from treemap.udf import UserDefinedCollectionValue

from djqscsv import write_csv, generate_filename
from exporter.models import ExportJob

from exporter.user import write_users
from exporter.util import sanitize_unicode_record


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


def values_for_model(
        instance, job, table, model,
        select, select_params, prefix=None):
    if prefix:
        prefix += '__'
    else:
        prefix = ''

    perms = permissions(job.user, instance, model)

    prefixed_names = []
    model_class = safe_get_model_class(model)
    dummy_instance = model_class()

    for perm in (perm for perm in perms
                 if perm.permission_level >= FieldPermission.READ_ONLY):
        field_name = perm.field_name
        prefixed_name = prefix + field_name

        if field_name in model_class.collection_udf_settings.items():

            field_definition_id = None
            for udfd in udf_defs(instance, model):
                if udfd.iscollection and udfd.name == field_name[4:]:
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
        elif field_name.startswith('udf:'):
            name = field_name[4:]
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


@task
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


@task
@_job_transaction
def async_species_csv_export(job):
    instance = job.instance

    select = OrderedDict()
    select_params = []

    initial_qs = Species.objects.filter(instance=instance)
    values = values_for_model(instance, job, 'treemap_species',
                              'Species', select, select_params)
    ordered_fields = values + select.keys()
    limited_qs = (initial_qs
                  .extra(select=select,
                         select_params=select_params)
                  .values(*ordered_fields))

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
                  field_order=ordered_fields)
        filename = generate_filename(limited_qs).replace('plot', 'tree')
        job.complete_with(filename, File(csv_file))

    job.save()


@task
@_job_transaction
def async_plot_csv_export(job, query, display_filters):
    instance = job.instance

    select = OrderedDict()
    select_params = []

    field_header_map = {}
    # TODO: if an anonymous job with the given query has been
    # done since the last update to the audit records table,
    # just return that job

    # get the plots for the provided
    # query and turn them into a tree queryset
    search_filter = Filter(query, display_filters, instance)
    initial_qs = search_filter.get_objects(Plot)

    benefits = TreeBenefitsCalculator().full_benefits_for_filter(
        instance, search_filter)

    values_tree = values_for_model(
        instance, job, 'treemap_tree', 'Tree',
        select, select_params,
        prefix='tree')
    values_plot = values_for_model(
        instance, job, 'treemap_mapfeature', 'Plot',
        select, select_params)
    values_sp = values_for_model(
        instance, job, 'treemap_species', 'Species',
        select, select_params,
        prefix='tree__species')

    if 'geom' in values_plot:
        values_plot = [f for f in values_plot if f != 'geom']
        values_plot += ['geom__x', 'geom__y']

    get_ll = 'ST_Transform(treemap_mapfeature.the_geom_webmercator, 4326)'
    select['geom__x'] = 'ST_X(%s)' % get_ll
    select['geom__y'] = 'ST_Y(%s)' % get_ll

    ordered_fields = (sorted(values_tree)
                      + sorted(values_plot)
                      + sorted(values_sp))

    if ordered_fields:
        limited_qs = (initial_qs
                      .extra(select=select,
                             select_params=select_params)
                      .values(*ordered_fields))

        ordered_fields += list(BenefitCategory.GROUPS)
        field_header_map = _csv_field_header_map(ordered_fields)
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

        writer = csv.DictWriter(csv_file, ordered_fields)
        writer.writerow(field_header_map)
        for row in limited_qs:
            tree_pk = str(row["tree__id"])
            if tree_pk in benefits:
                tree_benefits = {
                    factor: prop['value']
                    for factor, prop in benefits[tree_pk]['plot'].iteritems()}
                row.update(tree_benefits)

            writer.writerow(sanitize_unicode_record(row))

        filename = generate_filename(limited_qs).replace('plot', 'tree')
        job.complete_with(filename, File(csv_file))

    job.save()


def _csv_field_header_map(field_names):
    # Our query uses plot-centric field names but our csv wants tree-centric
    # header names. So convert e.g. "tree__canopy_height" -> "canopy_height"
    # and "width" -> "plot__width".
    map = {}
    for name in field_names:
        if name.startswith('tree__'):
            header = name[6:]
        elif name in BenefitCategory.GROUPS:
            header = name
        else:
            header = 'plot__%s' % name
        map[name] = header
    return map


@task
@_job_transaction
def simple_async_csv(job, qs):
    file_obj = TemporaryFile()
    write_csv(qs, file_obj)
    job.complete_with(generate_filename(qs), File(file_obj))
    job.save()


@task
def custom_async_csv(csv_rows, job_pk, filename, fields):
    with _job_transaction_manager(job_pk) as job:
        csv_obj = TemporaryFile()

        writer = csv.DictWriter(csv_obj, fields)
        writer.writeheader()
        for row in csv_rows:
            writer.writerow(sanitize_unicode_record(row))

        job.complete_with(filename, File(csv_obj))
        job.save()

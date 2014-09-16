# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from celery import task
from tempfile import TemporaryFile

from django.core.files import File
from treemap.lib.object_caches import permissions

from treemap.search import Filter
from treemap.models import Species, Tree

from djqscsv import write_csv, generate_filename
from exporter.models import ExportJob


def extra_select_and_values_for_model(
        instance, job, table, model, prefix=None):
    if prefix:
        prefix += '__'
    else:
        prefix = ''

    perms = permissions(job.user, instance, model)

    extra_select = {}
    prefixed_names = []

    for perm in perms:
        field_name = perm.field_name
        prefixed_name = prefix + field_name

        if field_name.startswith('udf:'):
            name = field_name[4:]
            extra_select[prefixed_name] = "%s.udfs->'%s'" % (table, name)

        prefixed_names.append(prefixed_name)

    return (extra_select, prefixed_names)


def csv_export(job_pk, model, query, display_filters):
    job = ExportJob.objects.get(pk=job_pk)
    instance = job.instance

    if model == 'species':
        initial_qs = (Species.objects.
                      filter(instance=instance))

        extra_select, values = extra_select_and_values_for_model(
            instance, job, 'treemap_species', 'species')
        ordered_fields = values + extra_select.keys()
        limited_qs = initial_qs.extra(select=extra_select)\
                               .values(*ordered_fields)
    else:
        # model == 'tree'

        # TODO: if an anonymous job with the given query has been
        # done since the last update to the audit records table,
        # just return that job

        # get the plots for the provided
        # query and turn them into a tree queryset
        initial_qs = Filter(query, display_filters, instance)\
            .get_objects(Tree)

        extra_select_tree, values_tree = extra_select_and_values_for_model(
            instance, job, 'treemap_tree', 'Tree')
        extra_select_plot, values_plot = extra_select_and_values_for_model(
            instance, job, 'treemap_mapfeature', 'Plot',
            prefix='plot')
        extra_select_sp, values_sp = extra_select_and_values_for_model(
            instance, job, 'treemap_species', 'Species',
            prefix='species')

        if 'plot__geom' in values_plot:
            values_plot = [f for f in values_plot if f != 'plot__geom']
            values_plot += ['plot__geom__x', 'plot__geom__y']

        extra_select = {'plot__geom__x':
                        'ST_X(treemap_mapfeature.the_geom_webmercator)',
                        'plot__geom__y':
                        'ST_Y(treemap_mapfeature.the_geom_webmercator)'}

        extra_select.update(extra_select_tree)
        extra_select.update(extra_select_plot)
        extra_select.update(extra_select_sp)

        ordered_fields = (sorted(values_tree) +
                          sorted(values_plot) +
                          sorted(values_sp))

        if ordered_fields:
            limited_qs = initial_qs.extra(select=extra_select)\
                                   .values(*ordered_fields)
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
        write_csv(limited_qs, csv_file, field_order=ordered_fields)
        job.complete_with(generate_filename(limited_qs), File(csv_file))

    job.save()

async_csv_export = task(csv_export)

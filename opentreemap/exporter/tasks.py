# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from celery import task
from tempfile import TemporaryFile

from django.core.files import File

from treemap.search import create_filter
from treemap.models import Species, Tree

from djqscsv import write_csv, generate_filename
from exporter.models import ExportJob


def extra_select_and_values_for_model(
        instance, user, table, model, prefix=None):
    if prefix:
        prefix += '__'
    else:
        prefix = ''

    perms = user.get_instance_permissions(instance,
                                          model)\
                .values_list('field_name', flat=True)

    extra_select = {}
    prefixed_names = []

    for perm in perms:
        prefixed_name = prefix + perm

        if perm.startswith('udf:'):
            name = perm[4:]
            extra_select[prefixed_name] = "%s.udfs->'%s'" % (table, name)

        prefixed_names.append(prefixed_name)

    return (extra_select, prefixed_names)


def csv_export(job_pk, model, query):
    job = ExportJob.objects.get(pk=job_pk)
    instance = job.instance

    if job.user and job.user.is_authenticated():
        if model == 'species':
            initial_qs = (Species.objects.
                          filter(instance=instance))

            extra_select, values = extra_select_and_values_for_model(
                instance, job.user, 'treemap_species', 'species')
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
            plot_query = (create_filter(query)
                          .filter(instance_id=instance.id))
            initial_qs = Tree.objects.filter(plot__in=plot_query)

            extra_select_tree, values_tree = extra_select_and_values_for_model(
                instance, job.user, 'treemap_tree', 'Tree')
            extra_select_plot, values_plot = extra_select_and_values_for_model(
                instance, job.user, 'treemap_mapfeature', 'Plot',
                prefix='plot')
            extra_select_sp, values_sp = extra_select_and_values_for_model(
                instance, job.user, 'treemap_species', 'Species',
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

            ordered_fields = (values_tree + extra_select_tree.keys() +
                              sorted(values_plot + extra_select_plot.keys()) +
                              sorted(values_sp + extra_select_sp.keys()))

            if ordered_fields:
                limited_qs = initial_qs.extra(select=extra_select)\
                                       .values(*ordered_fields)
            else:
                limited_qs = initial_qs.none()

    else:
        ordered_fields = None
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

        csv_name = generate_filename(limited_qs)
        job.outfile.save(csv_name, File(csv_file))
        job.status = ExportJob.COMPLETE

    job.save()

async_csv_export = task(csv_export)

# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from functools import wraps
from celery import chain

from exporter import (EXPORTS_NOT_ENABLED_CONTEXT,
                      EXPORTS_FEATURE_DISABLED_CONTEXT)
from exporter.lib import export_enabled_for
from exporter.models import ExportJob
from exporter.tasks import simple_async_csv, custom_async_csv


def queryset_as_exported_csv(fn):
    @wraps(fn)
    def wrapped_fn(request, instance, *args, **kwargs):
        if not instance.feature_enabled('exports'):
            return EXPORTS_FEATURE_DISABLED_CONTEXT
        elif not export_enabled_for(instance, request.user):
            return EXPORTS_NOT_ENABLED_CONTEXT

        qs = fn(request, instance, *args, **kwargs)

        job = ExportJob.objects.create(
            instance=instance,
            description="job created by '%s' fn" % fn,
            user=request.user)
        simple_async_csv.delay(job.pk, qs)

        return {'start_status': 'OK', 'job_id': job.pk}

    return wrapped_fn


def task_output_as_csv(fn):
    """Starts an async CSV export by calling a task with provided arguments
    Expects the decorated function to return a 4-tuple of:
        (filename, task, task_arguments_tuple, csv_fields)
    """
    @wraps(fn)
    def wrapped_fn(request, instance, *args, **kwargs):
        filename, task, args, fields = fn(request, instance, *args, **kwargs)

        if not instance.feature_enabled('exports'):
            return EXPORTS_FEATURE_DISABLED_CONTEXT
        elif not export_enabled_for(instance, request.user):
            return EXPORTS_NOT_ENABLED_CONTEXT

        job = ExportJob.objects.create(
            instance=instance,
            description="job created by '%s' fn" % fn,
            user=request.user)

        chain(task.s(*args) | custom_async_csv.s(job.pk, filename, fields))()

        return {'start_status': 'OK', 'job_id': job.pk}

    return wrapped_fn

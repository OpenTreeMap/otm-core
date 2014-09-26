# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from functools import wraps

from exporter.models import ExportJob
from exporter.tasks import simple_async_csv


def queryset_as_exported_csv(fn):
    @wraps(fn)
    def wrapped_fn(request, instance, *args, **kwargs):
        qs = fn(request, instance, *args, **kwargs)

        job = ExportJob.objects.create(
            instance=instance,
            description="job created by '%s' fn" % fn,
            user=request.user)
        simple_async_csv.delay(job.pk, qs)

        return {'start_status': 'OK', 'job_id': job.pk}

    return wrapped_fn

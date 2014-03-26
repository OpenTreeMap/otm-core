# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from exporter.models import ExportJob
from tasks import async_csv_export

from django.shortcuts import get_object_or_404

from treemap.decorators import (json_api_call, instance_request,
                                requires_feature)


def begin_export(request, instance, model):
    query = request.GET.get('q', None)
    display_filters = request.GET.get('show', None)

    job = ExportJob(instance=instance)

    if request.user.is_authenticated():
        job.user = request.user
    job.save()

    async_csv_export.delay(job.pk, model, query, display_filters)

    return {'start_status': 'OK', 'job_id': job.pk}


def check_export(request, instance, job_id):

    job = get_object_or_404(ExportJob, pk=job_id)

    # if a job has a user, it means the user must
    # be authenticated so only the job user can
    # retrieve the export
    if job.user and job.user != request.user:
        return {'status': 'ERROR',
                'message': 'Job not initiated by user',
                'url': None}

    else:
        return {'status': ExportJob.STATUS_STRINGS[job.status],
                'message': ExportJob.STATUS_CHOICES[job.status],
                'url': job.get_url_if_ready()}


begin_export_endpoint = json_api_call(
    instance_request(
        requires_feature('exports')(
            begin_export)))
check_export_endpoint = json_api_call(
    instance_request(
        requires_feature('exports')(
            check_export)))

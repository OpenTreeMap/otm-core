# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.http import Http404
from django.shortcuts import get_object_or_404

from tasks import async_csv_export, async_users_export

from django_tinsel.utils import decorate as do
from django_tinsel.decorators import json_api_call

from treemap.util import get_csv_response, get_json_response
from treemap.decorators import instance_request

from exporter import (EXPORTS_NOT_ENABLED_CONTEXT,
                      EXPORTS_FEATURE_DISABLED_CONTEXT)
from exporter.lib import export_enabled_for
from exporter.models import ExportJob
from exporter.user import write_users

############################################
# synchronous exports
############################################
#
# these are legacy views that are used by the API to provide
# this data to external services. they are not used by the web
# client (js) or the android app. generally, they should not
# be used, because synchronous exports are a costly burden
# on the request/response cycle.
#
# TODO: convert the API to provide asynchronous exporting.
#


def _get_user_extra_args(request):
    return [request.GET.get("minJoinDate"),
            request.GET.get("minEditDate")]


def users_csv(request, instance):
    "Return a user csv synchronously"
    response = get_csv_response('users.csv')
    extra = _get_user_extra_args(request)
    write_users('csv', response, instance, *extra)
    return response


def users_json(request, instance):
    response = get_json_response('user_export.json')
    extra = _get_user_extra_args(request)
    write_users('json', response, instance, *extra)
    return response


############################################
# async exports
############################################

def begin_export_users(request, instance, data_format):
    if not request.user.is_authenticated():
        raise Http404()

    if not instance.feature_enabled('exports'):
        return EXPORTS_FEATURE_DISABLED_CONTEXT
    elif not export_enabled_for(instance, request.user):
        return EXPORTS_NOT_ENABLED_CONTEXT

    job = ExportJob.objects.create(
        instance=instance,
        user=request.user,
        description='user export with %s format' % data_format)

    async_users_export.delay(job.pk, data_format)

    return {'start_status': 'OK', 'job_id': job.pk}


def begin_export(request, instance, model):
    if not instance.feature_enabled('exports'):
        return EXPORTS_FEATURE_DISABLED_CONTEXT
    elif not export_enabled_for(instance, request.user):
        return EXPORTS_NOT_ENABLED_CONTEXT

    query = request.GET.get('q', None)
    display_filters = request.GET.get('show', None)

    job = ExportJob(instance=instance,
                    description='csv export of %s' % model)

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


begin_export_endpoint = do(
    json_api_call,
    instance_request,
    begin_export)

check_export_endpoint = do(
    json_api_call,
    instance_request,
    check_export)

from celery import task
from djqscsv import make_csv_file, generate_filename

from django.core.files import File

from treemap.search import create_filter
from treemap.models import Species, Tree

from models import ExportJob


def csv_export(job_pk, model, query):

    job = ExportJob.objects.get(pk=job_pk)
    instance = job.instance

    if model == 'species':
        initial_qs = (Species.objects.
                      filter(instance=instance))
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

    # limit_fields_by_user exists on authorizable models/querysets
    # keep track of the before/after queryset to determine if empty
    # querysets were caused by authorization failure.
    if hasattr(initial_qs, 'limit_fields_by_user'):
        if job.user and job.user.is_authenticated():
            limited_qs = initial_qs.limit_fields_by_user(instance,
                                                         job.user)
        else:
            limited_qs = initial_qs.none()
    else:
        limited_qs = initial_qs

    if not initial_qs.exists():
        job.status = ExportJob.EMPTY_QUERYSET_ERROR

    # if the initial queryset was not empty but the limited queryset
    # is empty, it means that there were no fields which the user
    # was allowed to export.
    elif not limited_qs.exists():
        job.status = ExportJob.MODEL_PERMISSION_ERROR
    else:
        csv_file = make_csv_file(limited_qs)
        csv_name = generate_filename(limited_qs)
        job.outfile.save(csv_name, File(csv_file))
        job.status = ExportJob.COMPLETE

    job.save()

async_csv_export = task(csv_export)

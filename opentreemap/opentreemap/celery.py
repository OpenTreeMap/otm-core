from __future__ import absolute_import

import os

from celery import Celery
from celery.signals import task_failure


# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                      'opentreemap.settings')

app = Celery('opentreemap')

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# TODO: Enable when django-statsd is compatible with Django > 1.8
# if getattr(settings, 'STATSD_CELERY_SIGNALS', False):
#     # Import here to prevent error on Celery launch
#     # that settings module is not defined
#     from django_statsd.celery import register_celery_events
#     register_celery_events()


rollbar_setup = False


@task_failure.connect
def handle_task_failure(**kw):
    # Rollbar initialization has to be done lazily, or the server segfaults
    # when starting :(
    from django.conf import settings
    import rollbar
    global rollbar_setup

    rollbar_settings = getattr(settings, 'ROLLBAR', {})
    access_token = rollbar_settings.get('access_token')
    if access_token and not rollbar_setup:
        rollbar.init(access_token, rollbar_settings['environment'])
        rollbar_setup = True

    if access_token:
        rollbar.report_exc_info(extra_data=kw)

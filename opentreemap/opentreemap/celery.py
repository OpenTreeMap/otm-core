from __future__ import absolute_import

import os

import rollbar

from celery import Celery
from celery.signals import task_failure

from django.conf import settings

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                      'opentreemap.settings')

app = Celery('opentreemap')

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

rollbar_settings = getattr(settings, 'ROLLBAR', {})
access_token = rollbar_settings.get('access_token')
if access_token:
    rollbar.init(access_token, rollbar_settings['environment'])


@task_failure.connect
def handle_task_failure(**kw):
    if access_token:
        rollbar.report_exc_info(extra_data=kw)

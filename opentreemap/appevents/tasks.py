# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from celery import shared_task
from django.db import transaction
from django.utils.timezone import now
from django.conf import settings
from treemap.lib import get_function_by_path
from appevents.models import AppEvent

DEFAULT_HANDLER_PATH = 'appevents.handlers.default_handler'
HANDLER_SETTING = 'APPEVENT_HANDLERS'


@transaction.atomic
def _lookup_and_assign_handler(event_id):
    events = AppEvent.objects.filter(pk=event_id, handler_assigned_at=None)
    if len(events) == 1:
        event = events[0]
        event.handled_by = _get_handler_path_for_event(event)
        event.handler_assigned_at = now()
        event.save()
        return event
    else:
        return None


def _get_handler_path_for_event(event):
    """
    This function expects settings to define a mapping from string event_type
    to a path to an importable function:

    APPEVENT_HANDLERS = {
        'application.THING_CREATED': 'app.handlers.send_email'
    }
    """
    handler_paths = getattr(settings, HANDLER_SETTING, None)
    if handler_paths is None:
        return DEFAULT_HANDLER_PATH
    else:
        return handler_paths.get(event.event_type,
                                 DEFAULT_HANDLER_PATH)


@shared_task
def queue_events_to_be_handled():
    for event in AppEvent.objects.filter(handler_assigned_at=None):
        handle_event.delay(event.pk)


@shared_task
def handle_event(event_id):
    event = _lookup_and_assign_handler(event_id)
    if event is None:
        return

    event.handled_at = now()
    try:
        handler = get_function_by_path(event.handled_by)
    except Exception as e:
        event.handler_succeeded = False
        event.handler_log =\
            'Exception loading function %s: %s' % (event.handled_by, str(e))
    else:
        try:
            handler(event)
        except Exception as e:
            event.handler_succeeded = False
            event.handler_log =\
                'Unhandled exception thrown by %s: %s'\
                % (event.handled_by, str(e))

    event.save()

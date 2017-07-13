# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.db import models

from treemap.json_field import JSONField
from treemap.DotDict import DotDict


class AppEvent(models.Model):
    event_type = models.CharField(max_length=255)
    data = JSONField(blank=True, default=DotDict)
    triggered_at = models.DateTimeField(auto_now_add=True)
    handler_assigned_at = models.DateTimeField(null=True)
    handled_by = models.CharField(max_length=255, blank=True)
    handled_at = models.DateTimeField(null=True)
    handler_succeeded = models.NullBooleanField(null=True)
    handler_log = models.TextField(blank=True)

    @classmethod
    def create(cls, event_type, **kwargs):
        # TODO: If a callable is not associated with the event_type, throw
        app_event = AppEvent(event_type=event_type)
        for key, value in kwargs.iteritems():
            app_event.data[key] = value
        app_event.save()
        return app_event

# The signals need to be imported after the models are defined
import signals  # NOQA

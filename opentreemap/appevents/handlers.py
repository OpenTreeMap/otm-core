# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.utils.timezone import now


def default_handler(event):
    event.handled_at = now()
    event.handler_succeeded = True
    event.handler_log = 'No handler assigned'
    event.save()
    return event

# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.db.models.signals import post_save
from django.dispatch import receiver

from models import AppEvent

from tasks import queue_events_to_be_handled


@receiver(post_save, sender=AppEvent)
def queue_events_to_be_handled_receiver(sender, **kwargs):
    queue_events_to_be_handled.apply()

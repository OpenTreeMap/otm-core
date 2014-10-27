# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from treemap.tests.base import OTMTestCase
from appevents.models import AppEvent
from django.utils.timezone import now
from datetime import timedelta


class AppEventTests(OTMTestCase):
    def test_class_create(self):
        AppEvent.create('foo', key1='value1', key2='value2')
        created_event = AppEvent.objects.all()[0]
        self.assertTrue(created_event.triggered_at
                        > (now() - timedelta(minutes=1)))
        self.assertEqual('value1', created_event.data.key1)
        self.assertEqual('value2', created_event.data.key2)

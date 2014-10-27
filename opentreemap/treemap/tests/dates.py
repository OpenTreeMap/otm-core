# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division


from datetime import datetime
from django.utils import timezone

from treemap.tests.base import OTMTestCase
from treemap.lib.dates import datesafe_eq


class DatesafeEqTest(OTMTestCase):
    def test_tz_aware_eq(self):
        d = timezone.now()
        self.assertTrue(datesafe_eq(d, d))

    def test_tz_aware_neq(self):
        d1 = timezone.now()
        d2 = timezone.make_aware(datetime(d1.year, d1.month, d1.day,
                                          d1.hour, d1.minute, d1.second,
                                          d1.microsecond),
                                 timezone.get_default_timezone())
        self.assertFalse(datesafe_eq(d1, d2))

    def test_tz_naive_eq(self):
        d = timezone.now()
        self.assertTrue(datesafe_eq(d, d))

    def test_tz_naive_neq(self):
        d1 = datetime.now()
        d2 = datetime(d1.year, d1.month, d1.day, d1.hour - 1)
        self.assertFalse(datesafe_eq(d1, d2))

    def test_mixed_tz_awareness_eq(self):
        d1 = timezone.now()
        d2 = datetime(d1.year, d1.month, d1.day, d1.hour,
                      d1.minute, d1.second, d1.microsecond)
        self.assertTrue(datesafe_eq(d1, d2))

    def test_mixed_tz_awareness_neq(self):
        d1 = timezone.now()
        d2 = datetime(d1.year, d1.month, d1.day, d1.hour - 1)
        self.assertFalse(datesafe_eq(d1, d2))

    def test_non_dates_eq(self):
        self.assertTrue(datesafe_eq(4, 4))

    def test_non_dates_neq(self):
        self.assertFalse(datesafe_eq(4, 5))

    def test_mixed_types_date_and_non_date_neq(self):
        d = datetime.now()
        self.assertFalse(datesafe_eq(d, 5))

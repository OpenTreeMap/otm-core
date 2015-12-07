# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.contrib.gis.geos import Point
from django.db.models import Count

from treemap.models import Plot
from treemap.lib.hide_at_zoom import (recompute_hide_at_zoom,
                                      update_hide_at_zoom_after_delete,
                                      update_hide_at_zoom_after_move)
from treemap.tests import make_instance, make_commander_user
from treemap.tests.base import OTMTestCase


class HideAtZoomTests(OTMTestCase):
    def setUp(self):
        self.instance = make_instance(edge_length=1000)
        self.user = make_commander_user(self.instance)
        self.make_plots([
            (0, 100), (0, 101), (0, 200), (0, 201)
        ])
        recompute_hide_at_zoom(self.instance)
        # Two plots have hide_at_zoom == 14
        # One plot has hide_at_zoom == 10
        # One plot has hide_at_zoom == None
        self.assert_counts({14: 2, 10: 1})

    def make_plots(self, points):
        for p in points:
            plot = Plot(instance=self.instance, geom=Point(*p))
            plot.save_with_user(self.user)

    def assert_counts(self, expected_count_dict):
        # Count occurrences of each hide_at_zoom value
        counts = Plot.objects.values('hide_at_zoom') \
            .annotate(count=Count('hide_at_zoom'))
        # Put counts into a dict.
        # Skip "None" values because they aren't counted correctly.
        # (The assert is still strong because an unexpected number of "None"
        # values would be matched by an unexpected number of some other value.)
        count_dict = {c['hide_at_zoom']: c['count'] for c in counts
                      if c['hide_at_zoom'] is not None}
        self.assertEqual(count_dict, expected_count_dict)

    def delete_and_assert_counts(self, plot, expected_count_dict):
        plot.delete_with_user(self.user)
        update_hide_at_zoom_after_delete(plot)
        self.assert_counts(expected_count_dict)

    def move_and_assert_counts(self, plot, new_point, expected_count_dict):
        old_point = plot.geom
        plot.geom = Point(*new_point)
        plot.save_with_user(self.user)
        update_hide_at_zoom_after_move(plot, self.user, old_point)
        self.assert_counts(expected_count_dict)

    def test_delete_1(self):
        plot = Plot.objects.get(hide_at_zoom=None)
        self.delete_and_assert_counts(plot, {14: 1, 10: 1})

    def test_delete_2(self):
        plot = Plot.objects.get(hide_at_zoom=10)
        self.delete_and_assert_counts(plot, {14: 1, 10: 1})

    def test_move_1(self):
        plot = Plot.objects.get(hide_at_zoom=None)
        point = (1, plot.geom.y)
        self.move_and_assert_counts(plot, point, {14: 1, 10: 1})

    def test_move_2(self):
        plot = Plot.objects.get(hide_at_zoom=10)
        point = (1, plot.geom.y)
        self.move_and_assert_counts(plot, point, {14: 1, 10: 1})

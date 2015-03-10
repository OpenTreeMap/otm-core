# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import pytz

from datetime import datetime, timedelta

from django.contrib.gis.geos import Point
from django.db.models import Q
from django.utils import timezone

from treemap.lib import execute_sql
from treemap.lib.map_feature import set_map_feature_updated_at
from treemap.models import Tree, Plot, Audit
from treemap.tests import (LocalMediaTestCase, make_instance,
                           make_commander_user)


class UpdatedAtTestCase(LocalMediaTestCase):
    def setUp(self):
        super(UpdatedAtTestCase, self).setUp()
        self.image = self.load_resource('tree1.gif')
        self.test_start = timezone.now()
        self.point = Point(-8515941.0, 4953519.0)
        self.instance = make_instance(point=self.point)
        self.user = make_commander_user(self.instance)
        self.plot = Plot(geom=self.point, instance=self.instance)
        self.plot.save_with_user(self.user)

    def reload_members(self):
        self.plot = Plot.objects.get(pk=self.plot.pk)

    def max_audit_for_model_type(self, models):
        if isinstance(models, basestring):
            models = [models]
        model_q = Q()
        for model in models:
            model_q |= Q(model=model)
        audits = Audit.objects.filter(model_q)\
                              .order_by('-created')

        if audits:
            return audits[0]

    def clear_updated_at(self):
        # to_timestamp(0) is the unix epoch 1970-1-1 00:00
        execute_sql(
            "UPDATE treemap_mapfeature SET updated_at = to_timestamp(0);")

    def clear_and_set_and_reload(self):
        self.clear_updated_at()
        set_map_feature_updated_at()
        self.reload_members()

    def test_helpers(self):
        self.clear_updated_at()
        self.reload_members()
        self.assertEqual(self.plot.updated_at,
                         datetime(1970, 1, 1, tzinfo=pytz.UTC))

    def test_map_feature_is_updated(self):
        self.clear_and_set_and_reload()
        self.assertGreater(self.plot.updated_at, self.test_start)

    def test_tree_overrides_plot(self):
        tree = Tree(diameter=10, plot=self.plot, instance=self.instance)
        tree.save_with_user(self.user)

        tree_audit = self.max_audit_for_model_type('Tree')
        plot_audit = self.max_audit_for_model_type('Plot')
        # Backdate the plot audit so it is definitely older than the tree audit
        plot_audit.created = tree_audit.created - timedelta(days=1)
        plot_audit.save()

        self.clear_and_set_and_reload()
        self.assertEqual(self.plot.updated_at, tree_audit.created)

    def test_treephoto_overrides_tree_and_plot_updated(self):
        tree = Tree(diameter=10, plot=self.plot, instance=self.instance)
        tree.save_with_user(self.user)
        tree.add_photo(self.image, self.user)

        tree_audit = self.max_audit_for_model_type('Tree')
        treephoto_audit = self.max_audit_for_model_type(['MapFeaturePhoto',
                                                         'TreePhoto'])
        plot_audit = self.max_audit_for_model_type('Plot')
        # Backdate the audits so photo it is definitely the newsest
        plot_audit.created = treephoto_audit.created - timedelta(days=2)
        plot_audit.save()
        tree_audit.created = treephoto_audit.created - timedelta(days=1)
        tree_audit.save()

        self.clear_and_set_and_reload()
        self.assertEqual(self.plot.updated_at, treephoto_audit.created)

# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import pytz

from datetime import datetime, timedelta

from django.contrib.gis.geos import Point
from django.utils import timezone

from treemap.lib import execute_sql
from treemap.lib.map_feature import (set_map_feature_updated_at,
                                     set_map_feature_updated_by)
from treemap.models import Tree, Plot, Audit
from treemap.tests import (LocalMediaTestCase, make_instance,
                           make_commander_user, make_user_with_default_role)


class UpdateTestCase(LocalMediaTestCase):
    def setUp(self):
        super(UpdateTestCase, self).setUp()
        self.image = self.load_resource('tree1.gif')
        self.test_start = timezone.now()
        self.point = Point(-8515941.0, 4953519.0)
        self.instance = make_instance(point=self.point)
        self.user = make_commander_user(self.instance)
        self.plot = Plot(geom=self.point, instance=self.instance)
        self.plot.save_with_user(self.user)

    def max_audit_for_model_type(self, models):
        if isinstance(models, basestring):
            models = [models]
        audits = Audit.objects.filter(model__in=models)\
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
        self.plot.refresh_from_db()


class UpdatedAtTest(UpdateTestCase):

    def test_helpers(self):
        self.clear_updated_at()
        self.plot.refresh_from_db()
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


class UpdatedByTest(UpdateTestCase):

    def setUp(self):
        super(UpdatedByTest, self).setUp()
        self.other = make_commander_user(instance=self.instance,
                                         username='other')
        self.default_user = make_user_with_default_role(
            instance=self.instance, username='default')

        self.other.save()
        self.default_user.save()
        self.other.refresh_from_db()
        self.default_user.refresh_from_db()

    def clear_updated_by(self):
        execute_sql(
            "UPDATE treemap_mapfeature SET updated_by_id = {};".format(
                self.default_user.pk))

    def clear_and_set_and_reload(self):
        self.clear_updated_by()
        set_map_feature_updated_by()
        self.plot.refresh_from_db()

    def test_helpers(self):
        self.clear_updated_by()
        self.plot.refresh_from_db()
        self.assertEqual(self.plot.updated_by, self.default_user)

    def test_map_feature_is_updated_by(self):
        self.clear_and_set_and_reload()
        self.assertEqual(self.plot.updated_by_id, self.user.pk)

        self.plot.width = 24.0
        self.plot.save_with_user(self.other)
        self.clear_and_set_and_reload()
        self.assertEqual(self.plot.updated_by_id, self.other.pk)

    def test_tree_overrides_plot(self):
        tree = Tree(diameter=10, plot=self.plot, instance=self.instance)
        tree.save_with_user(self.other)

        self.clear_and_set_and_reload()
        self.assertEqual(self.plot.updated_by_id, self.other.pk)

    def test_treephoto_overrides_tree_and_plot(self):
        tree = Tree(diameter=10, plot=self.plot, instance=self.instance)
        tree.save_with_user(self.user)
        tree.add_photo(self.image, self.other)

        self.clear_and_set_and_reload()
        self.assertEqual(self.plot.updated_by_id, self.other.pk)

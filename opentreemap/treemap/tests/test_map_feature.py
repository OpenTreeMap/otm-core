# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from contextlib import contextmanager
from unittest.case import skip

from django.contrib.gis.geos import Point

from treemap.models import (Tree, Plot, MapFeature)
from treemap.instance import Instance
from treemap.tests import (make_instance, make_commander_user)
from treemap.tests.base import OTMTestCase
from treemap.views.map_feature import update_map_feature


class GeoRevIncr(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.user = make_commander_user(self.instance)
        self.plot = Plot(geom=Point(0, 0), instance=self.instance)
        self.plot.save_with_user(self.user)

    def _hash_and_rev(self):
        i = Instance.objects.get(pk=self.instance.pk)
        return [i.geo_rev_hash, i.geo_rev]

    @contextmanager
    def _assert_updates_geo_rev(self, update_expected=True):
        rev1h, rev1 = self._hash_and_rev()

        yield

        rev2h, rev2 = self._hash_and_rev()
        if update_expected:
            self.assertNotEqual(rev1h, rev2h)
            self.assertEqual(rev1 + 1, rev2)
        else:
            self.assertEqual(rev1h, rev2h)
            self.assertEqual(rev1, rev2)

    def test_create(self):
        with self._assert_updates_geo_rev():
            plot = Plot(instance=self.instance)
            request_dict = {'plot.geom': {'x': 0, 'y': 0}}
            update_map_feature(request_dict, self.user, plot)
            plot.save_with_user(self.user)

    def test_move(self):
        with self._assert_updates_geo_rev():
            request_dict = {'plot.geom': {'x': 5, 'y': 5}}
            update_map_feature(request_dict, self.user, self.plot)
            self.plot.save_with_user(self.user)

    def test_update_without_move(self):
        with self._assert_updates_geo_rev(False):
            request_dict = {'plot.address_zip': '19119'}
            update_map_feature(request_dict, self.user, self.plot)
            self.plot.save_with_user(self.user)

    def test_delete(self):
        with self._assert_updates_geo_rev():
            self.plot.delete_with_user(self.user)


class PlotHashTestCase(OTMTestCase):
    """
    Test that plot functionality works when moving
    between instances of the generic MapFeature model
    and the concrete Plot model
    """
    def setUp(self):
        point = Point(-8515941.0, 4953519.0)
        instance = make_instance(point=point)
        user = make_commander_user(instance)
        plot = Plot(geom=point, instance=instance)
        plot.save_with_user(user)

        self.user = user
        self.instance = instance
        self.plot_obj = Plot.objects.get(instance=instance)
        self.map_feature_obj = MapFeature.objects.get(instance=instance)

    def test_is_plot_with_plot_instance(self):
        self.assertEqual(self.plot_obj.is_plot, True)

    def test_is_plot_with_map_feature_instance(self):
        self.assertEqual(self.map_feature_obj.is_plot, True)

    def _test_hash_setup(self):
        self.initial_plot_hash = self.plot_obj.hash
        self.initial_map_feature_hash = self.map_feature_obj.hash

        # adding a tree should change the plot hash
        tree = Tree(diameter=10, plot=self.plot_obj, instance=self.instance)
        tree.save_with_user(self.user)
        self.final_plot_hash = self.plot_obj.hash
        self.final_map_feature_hash = self.map_feature_obj.hash

    def test_hash_changes(self):
        self._test_hash_setup()
        add_tree_msg = "Adding a tree should always change the hash"
        self.assertNotEqual(self.initial_plot_hash,
                            self.final_plot_hash,
                            add_tree_msg)
        self.assertNotEqual(self.initial_map_feature_hash,
                            self.final_map_feature_hash,
                            add_tree_msg)

    @skip("This feature is probably too hard to support")
    def test_hash_same_for_plot_and_map_feature(self):
        # TODO: it would be great to support this, but the hashes
        # are different because the .hash property on Authorizable
        # uses the ._model_name property of a model as part of the hash.
        # changing ._model_name by overriding it on MapFeature is viable
        # but could have unexpected consequences in the audit system.
        # unfortunately, it's probably not worth the effort.
        self._test_hash_setup()
        same_hash_msg = ("The plot has should be the same whether you "
                         "get it from a Plot or MapFeature")
        self.assertEqual(self.initial_plot_hash,
                         self.initial_map_feature_hash,
                         same_hash_msg)
        self.assertEqual(self.final_plot_hash,
                         self.final_map_feature_hash,
                         same_hash_msg)


class UpdatedAtTest(OTMTestCase):

    def setUp(self):
        self.point = Point(-8515941.0, 4953519.0)
        self.instance = make_instance(point=self.point)
        self.user = make_commander_user(self.instance)
        self.plot = Plot(geom=self.point, instance=self.instance)
        self.plot.save_with_user(self.user)
        self.plot = Plot.objects.get(pk=self.plot.pk)
        self.initial_updated = self.plot.updated_at

    def test_update_sets_updated(self):
        self.plot.width = 22
        self.plot.save_with_user(self.user)
        self.assertGreater(self.plot.updated_at, self.initial_updated)

    def test_add_tree_sets_updated(self):
        tree = Tree(diameter=10, plot=self.plot, instance=self.instance)
        tree.save_with_user(self.user)
        self.assertGreater(self.plot.updated_at, self.initial_updated)

    def test_update_tree_sets_updated(self):
        tree = Tree(diameter=10, plot=self.plot, instance=self.instance)
        tree.save_with_user(self.user)
        self.plot = Plot.objects.get(pk=self.plot.pk)
        self.inital_updated = self.plot.updated_at

        tree.height = 22
        tree.save_with_user(self.user)
        self.assertGreater(self.plot.updated_at, self.initial_updated)

    def test_delete_tree_sets_updated(self):
        tree = Tree(diameter=10, plot=self.plot, instance=self.instance)
        tree.save_with_user(self.user)
        self.plot = Plot.objects.get(pk=self.plot.pk)
        self.inital_updated = self.plot.updated_at

        tree.delete_with_user(self.user)
        self.assertGreater(self.plot.updated_at, self.initial_updated)

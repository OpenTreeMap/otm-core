# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from contextlib import contextmanager
from unittest.case import skip

from django.contrib.gis.geos import Point

from treemap.models import (Tree, Plot, MapFeature, Species)
from treemap.instance import Instance
from treemap.tests import (make_instance, make_commander_user)
from treemap.tests.base import OTMTestCase
from treemap.views.map_feature import update_map_feature

from stormwater.models import Bioswale


class GeoAndEcoRevIncr(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.user = make_commander_user(self.instance)
        self.plot = Plot(geom=Point(0, 0), instance=self.instance)
        self.plot.save_with_user(self.user)

    def _hash_and_revs(self):
        i = Instance.objects.get(pk=self.instance.pk)
        return [i.geo_rev_hash, i.geo_rev, i.eco_rev]

    @contextmanager
    def _assert_updates_geo_and_eco_rev(self, update_expected=True):
        geo_rev1h, geo_rev1, eco_rev1 = self._hash_and_revs()

        yield

        geo_rev2h, geo_rev2, eco_rev2 = self._hash_and_revs()

        if update_expected:
            self.assertNotEqual(geo_rev1h, geo_rev2h)
            self.assertEqual(geo_rev1 + 1, geo_rev2)
            self.assertEqual(eco_rev1 + 1, eco_rev2)
        else:
            self.assertEqual(geo_rev1h, geo_rev2h)
            self.assertEqual(geo_rev1, geo_rev2)
            self.assertEqual(eco_rev1, eco_rev2)

    def test_create_plot(self):
        with self._assert_updates_geo_and_eco_rev():
            plot = Plot(instance=self.instance)
            request_dict = {'plot.geom': {'x': 0, 'y': 0}}
            update_map_feature(request_dict, self.user, plot)

    def test_create_bioswale(self):
        self.instance.add_map_feature_types(['Bioswale'])
        with self._assert_updates_geo_and_eco_rev():
            bioswale = Bioswale(instance=self.instance)
            request_dict = {
                'plot.geom': {'x': 0, 'y': 0},
                'bioswale.polygon': {'polygon': [
                    [0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]}
            }
            update_map_feature(request_dict, self.user, bioswale)

        with self._assert_updates_geo_and_eco_rev():
            request_dict = {
                'bioswale.polygon': {'polygon': [
                    [0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]}}
            update_map_feature(request_dict, self.user, bioswale)

    def test_move(self):
        with self._assert_updates_geo_and_eco_rev():
            request_dict = {'plot.geom': {'x': 5, 'y': 5}}
            update_map_feature(request_dict, self.user, self.plot)

    def test_update_without_move(self):
        with self._assert_updates_geo_and_eco_rev(False):
            request_dict = {'plot.address_zip': '19119'}
            update_map_feature(request_dict, self.user, self.plot)

    def test_delete(self):
        with self._assert_updates_geo_and_eco_rev():
            self.plot.delete_with_user(self.user)


class EcoRevIncr(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.user = make_commander_user(self.instance)
        self.plot = Plot(geom=Point(0, 0), instance=self.instance)
        self.plot.save_with_user(self.user)

    def _get_eco_rev(self):
        i = Instance.objects.get(pk=self.instance.pk)
        return i.eco_rev

    @contextmanager
    def _assert_updates_eco_rev(self, update_expected=True):
        rev1 = self._get_eco_rev()

        yield

        rev2 = self._get_eco_rev()
        if update_expected:
            self.assertEqual(rev1 + 1, rev2)
        else:
            self.assertEqual(rev1, rev2)

    def test_update_diameter(self):
        with self._assert_updates_eco_rev(True):
            tree = Tree(instance=self.instance, plot=self.plot, diameter=3)
            tree.save_with_user(self.user)
            request_dict = {'tree.diameter': '5'}
            update_map_feature(request_dict, self.user, self.plot)

    def test_update_species(self):
        with self._assert_updates_eco_rev(True):
            tree = Tree(instance=self.instance, plot=self.plot)
            tree.save_with_user(self.user)
            species = Species(common_name='foo', instance=self.instance)
            species.save_with_user(self.user)
            request_dict = {'tree.species': species.pk}
            update_map_feature(request_dict, self.user, self.plot)


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

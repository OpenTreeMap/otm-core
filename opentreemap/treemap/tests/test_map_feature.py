# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from contextlib import contextmanager
from unittest.case import skip

from django.contrib.gis.geos import Point, MultiPolygon, Polygon
from django.test.utils import override_settings

from treemap.models import Tree, Plot, MapFeature, Species, TreePhoto
from treemap.instance import Instance
from treemap.search import Filter
from treemap.lib import format_benefits
from treemap.ecobenefits import get_benefits_for_filter, BenefitCategory
from treemap.tests import (make_instance, make_commander_user,
                           LocalMediaTestCase)
from treemap.tests.base import OTMTestCase
from treemap.tests.test_ecobenefits import EcoTestCase
from treemap.views.map_feature import update_map_feature

from stormwater.models import Bioswale


# this decorator is necessary in order to `add_map_feature_types(['Bioswale'])`
# in `test_create_bioswale`.
@override_settings(FEATURE_BACKEND_FUNCTION=None)
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


# this decorator is necessary in order to `add_map_feature_types(['Bioswale'])`
# in `setUp`.
@override_settings(FEATURE_BACKEND_FUNCTION=None)
class ResourceEcoBenefitsTest(EcoTestCase):
    def setUp(self):
        # sets up self.instance, self.user, self.species
        super(ResourceEcoBenefitsTest, self).setUp()
        self.instance.add_map_feature_types(['Bioswale'])
        diversion_rate = .85
        Bioswale.set_config_property(self.instance, 'diversion_rate',
                                     diversion_rate)
        Bioswale.set_config_property(self.instance, 'should_show_eco', True)
        self.instance.annual_rainfall_inches = 8.0

    def _center_as_3857(self):
        p = self.instance.center
        if p.srid != 3857:
            p.transform(3857)
        return p

    def _box_around_point(self, pt, edge=1.0):
        half_edge = 0.5 * edge
        x_min = pt.x - half_edge
        y_min = pt.y - half_edge
        x_max = pt.x + half_edge
        y_max = pt.y + half_edge
        poly = Polygon(((x_min, y_min),
                        (x_min, y_max),
                        (x_max, y_max),
                        (x_max, y_min),
                        (x_min, y_min)))
        return MultiPolygon((poly, ))

    def test_resource_ecobenefits(self):
        p = self._center_as_3857()
        box = self._box_around_point(p)
        bioswale = Bioswale(instance=self.instance,
                            geom=p,
                            polygon=box,
                            feature_type='Bioswale',
                            drainage_area=100.0)
        bioswale.save_with_user(self.user)
        filter = Filter('', '', self.instance)
        benefits, __ = get_benefits_for_filter(filter)

        self.assertIn('resource', benefits)
        resource_benefits = benefits['resource']
        self.assertIn(BenefitCategory.STORMWATER, resource_benefits)
        stormwater = resource_benefits[BenefitCategory.STORMWATER]
        self.assertTrue(isinstance(stormwater['value'], float))
        self.assertGreater(stormwater['value'], 0.0)
        self.assertTrue(isinstance(stormwater['currency'], float))
        self.assertEqual(stormwater['value'], stormwater['currency'])

    def test_all_ecobenefits(self):
        p = self._center_as_3857()
        plot = Plot(geom=p, instance=self.instance)
        plot.save_with_user(self.user)

        tree = Tree(plot=plot,
                    instance=self.instance,
                    readonly=False,
                    species=self.species,
                    diameter=1630)

        tree.save_with_user(self.user)

        p.x += 1.1
        p.y += 1.1
        box = self._box_around_point(p)
        bioswale = Bioswale(instance=self.instance,
                            geom=p,
                            polygon=box,
                            feature_type='Bioswale',
                            drainage_area=100.0)
        bioswale.save_with_user(self.user)
        filter = Filter('', '', self.instance)
        benefits, basis = get_benefits_for_filter(filter)

        self.assertIn('plot', benefits)
        plot_benefits = benefits['plot']
        plot_categories = set(plot_benefits.keys())
        self.assertSetEqual(plot_categories, set(BenefitCategory.GROUPS))

        plot_currencies = {
            cat: benefit.get('currency', None)
            for cat, benefit in plot_benefits.items()}
        self.assertIsNotNone(min(plot_currencies.values()))

        expected_total_currency = sum(
            [benefit['currency'] for benefit in plot_benefits.values()]) - \
            plot_benefits[BenefitCategory.CO2STORAGE]['currency'] + \
            benefits['resource'][BenefitCategory.STORMWATER]['currency']

        formatted = format_benefits(self.instance, benefits, basis, digits=0)
        self.assertAlmostEqual(formatted['benefits_total_currency'],
                               expected_total_currency, 3)


class UpdatedFieldsTest(LocalMediaTestCase):

    def setUp(self):
        super(UpdatedFieldsTest, self).setUp()

        self.point = Point(-8515941.0, 4953519.0)
        self.instance = make_instance(point=self.point)
        self.user = make_commander_user(self.instance)
        self.fellow = make_commander_user(self.instance, 'other-commander')
        self.plot = Plot(geom=self.point, instance=self.instance)
        self.plot.save_with_user(self.user)
        self.plot.refresh_from_db()
        self.initial_updated = self.plot.updated_at

    def test_initial_updated_by(self):
        self.assertEqual(self.plot.updated_by, self.user)

    def test_update_sets_updated(self):
        self.plot.width = 22
        self.plot.save_with_user(self.fellow)
        self.assertGreater(self.plot.updated_at, self.initial_updated)
        self.assertEqual(self.plot.updated_by, self.fellow)

    def test_add_tree_sets_updated(self):
        tree = Tree(diameter=10, plot=self.plot, instance=self.instance)
        tree.save_with_user(self.fellow)
        self.plot.refresh_from_db()
        self.assertGreater(self.plot.updated_at, self.initial_updated)
        self.assertEqual(self.plot.updated_by, self.fellow)

    def test_update_tree_sets_updated(self):
        tree = Tree(diameter=10, plot=self.plot, instance=self.instance)
        tree.save_with_user(self.user)
        self.plot.refresh_from_db()
        self.inital_updated = self.plot.updated_at

        tree.height = 22
        tree.save_with_user(self.fellow)
        self.plot.refresh_from_db()
        self.assertGreater(self.plot.updated_at, self.initial_updated)
        self.assertEqual(self.plot.updated_by, self.fellow)

    def test_delete_tree_sets_updated(self):
        tree = Tree(diameter=10, plot=self.plot, instance=self.instance)
        tree.save_with_user(self.user)
        self.plot.refresh_from_db()
        self.inital_updated = self.plot.updated_at

        tree.delete_with_user(self.fellow)
        self.plot.refresh_from_db()
        self.assertGreater(self.plot.updated_at, self.initial_updated)
        self.assertEqual(self.plot.updated_by, self.fellow)

    def test_add_photo_sets_updated(self):
        tree = Tree(diameter=10, plot=self.plot, instance=self.instance)
        tree.save_with_user(self.user)
        photo = TreePhoto(instance=self.instance,
                          map_feature=self.plot, tree=tree)
        photo.set_image(self.load_resource('tree1.gif'))
        photo.save_with_user(self.fellow)
        self.plot.refresh_from_db()
        self.assertGreater(self.plot.updated_at, self.initial_updated)
        self.assertEqual(self.plot.updated_by, self.fellow)

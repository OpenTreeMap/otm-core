# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import unittest

from treemap.ecobenefits import (FEET_SQ_PER_METER_SQ, FEET_PER_INCH,
                                 GALLONS_PER_CUBIC_FT)
from treemap.lib import perms
from treemap.lib.udf import udf_create
from treemap.models import MapFeature, MapFeaturePhoto
from treemap.search import Filter
from treemap.tests.test_udfs import UdfCRUTestCase
from treemap.tests import (make_instance, make_commander_user,
                           make_tweaker_role, make_user)
from treemap.tests.test_perms import PermissionsTestCase
from treemap.tests.base import OTMTestCase
from django.contrib.gis.geos import Point, Polygon, MultiPolygon
from django.test.utils import override_settings

from stormwater.models import Bioswale, RainGarden, RainBarrel


@override_settings(FEATURE_BACKEND_FUNCTION=None)
class UdfGenericCreateTest(UdfCRUTestCase):
    def test_non_treemap_model(self):
        self.instance.add_map_feature_types(['Bioswale'])

        body = {'udf.name': 'Testing choice',
                'udf.model': 'Bioswale',
                'udf.type': 'string'}

        udf_create(body, self.instance)


@override_settings(FEATURE_BACKEND_FUNCTION=None)
class ResourcePermsTest(PermissionsTestCase):
    def setUp(self):
        super(ResourcePermsTest, self).setUp()
        self.instance.add_map_feature_types(['RainBarrel', 'Bioswale'])
        self.role_no = make_tweaker_role(self.instance, 'no')
        self.commander = make_commander_user(self.instance)

    def _create_rainbarrel_return_map_feature(self):
        # Create a RainBarrel, but return the MapFeature
        # referenced by it, to make sure the permission codename
        # is constructed correctly even when passed a MapFeature.
        rainbarrel = RainBarrel(instance=self.instance, geom=self.p,
                                capacity=50.0)
        rainbarrel.save_with_user(self.commander)
        rainbarrel.refresh_from_db()
        return MapFeature.objects.get(pk=rainbarrel.pk)

    def test_map_feature_is_creatable(self):
        self._add_builtin_permission(self.role_yes, RainBarrel,
                                     'add_rainbarrel')
        self.assertTrue(
            perms.map_feature_is_creatable(self.role_yes, RainBarrel))

    def test_any_resource_is_creatable(self):
        self._add_builtin_permission(self.role_yes, RainBarrel,
                                     'add_rainbarrel')
        self.assertTrue(
            perms.any_resource_is_creatable(self.role_yes))

    def test_map_feature_is_not_creatable(self):
        self.assertFalse(
            perms.map_feature_is_creatable(self.role_no, RainBarrel))

    def test_no_resource_is_creatable(self):
        self.assertFalse(
            perms.any_resource_is_creatable(self.role_no))

    def test_rainbarrel_photo_is_addable(self):
        self._add_builtin_permission(self.role_yes, MapFeaturePhoto,
                                     'add_rainbarrelphoto')
        rainbarrel = self._create_rainbarrel_return_map_feature()
        self.assertTrue(perms.photo_is_addable(self.role_yes, rainbarrel))

    def test_rainbarrel_photo_is_not_addable(self):
        self._add_builtin_permission(self.role_no, RainBarrel,
                                     'add_rainbarrel')
        self._add_builtin_permission(self.role_no, Bioswale,
                                     'add_bioswale')
        self._add_builtin_permission(self.role_no, MapFeaturePhoto,
                                     'add_bioswalephoto')
        rainbarrel = self._create_rainbarrel_return_map_feature()
        self.assertFalse(perms.photo_is_addable(self.role_no, rainbarrel))

    def test_user_can_create_rainbarrel_photo(self):
        self._add_builtin_permission(self.role_yes, MapFeaturePhoto,
                                     'add_rainbarrelphoto')
        rainbarrel = self._create_rainbarrel_return_map_feature()
        user_yes = make_user(instance=self.instance,
                             make_role=lambda inst: self.role_yes)
        photo = MapFeaturePhoto(instance=self.instance,
                                map_feature=rainbarrel)
        photo.set_image(self.load_resource('tree1.gif'))
        self.assertTrue(photo.user_can_create(user_yes))

    def test_user_cannot_create_rainbarrel_photo(self):
        self._add_builtin_permission(self.role_no, RainBarrel,
                                     'add_rainbarrel')
        self._add_builtin_permission(self.role_no, Bioswale,
                                     'add_bioswale')
        self._add_builtin_permission(self.role_no, MapFeaturePhoto,
                                     'add_bioswalephoto')
        rainbarrel = self._create_rainbarrel_return_map_feature()
        user_no = make_user(instance=self.instance,
                            make_role=lambda inst: self.role_no)
        photo = MapFeaturePhoto(instance=self.instance,
                                map_feature=rainbarrel)
        photo.set_image(self.load_resource('tree1.gif'))
        self.assertFalse(photo.user_can_create(user_no))

    def test_rainbarrel_photo_is_deletable(self):
        rainbarrel = self._create_rainbarrel_return_map_feature()
        image = self.load_resource('tree1.gif')

        photo = rainbarrel.add_photo(image, self.commander)

        self._add_builtin_permission(self.role_yes, MapFeaturePhoto,
                                     'delete_rainbarrelphoto')
        user_yes = make_user(instance=self.instance,
                             make_role=lambda inst: self.role_yes)
        self.assertTrue(
            perms.is_deletable(user_yes.get_instance_user(self.instance),
                               photo))

    def test_rainbarrel_photo_is_not_deletable(self):
        rainbarrel = self._create_rainbarrel_return_map_feature()
        image = self.load_resource('tree1.gif')

        photo = rainbarrel.add_photo(image, self.commander)

        self._add_builtin_permission(self.role_no, RainBarrel,
                                     'delete_rainbarrel')
        self._add_builtin_permission(self.role_no, Bioswale,
                                     'delete_bioswale')
        self._add_builtin_permission(self.role_no, MapFeaturePhoto,
                                     'delete_bioswalephoto')
        user_no = make_user(instance=self.instance,
                            make_role=lambda inst: self.role_no)
        self.assertFalse(
            perms.is_deletable(user_no.get_instance_user(self.instance),
                               photo))

    def test_user_can_delete_rainbarrel_photo(self):
        rainbarrel = self._create_rainbarrel_return_map_feature()
        image = self.load_resource('tree1.gif')

        photo = rainbarrel.add_photo(image, self.commander)

        self._add_builtin_permission(self.role_yes, MapFeaturePhoto,
                                     'delete_rainbarrelphoto')
        user_yes = make_user(instance=self.instance,
                             make_role=lambda inst: self.role_yes)
        self.assertTrue(photo.user_can_delete(user_yes))

    def test_user_cannot_delete_rainbarrel_photo(self):
        rainbarrel = self._create_rainbarrel_return_map_feature()
        image = self.load_resource('tree1.gif')

        photo = rainbarrel.add_photo(image, self.commander)

        self._add_builtin_permission(self.role_no, RainBarrel,
                                     'delete_rainbarrel')
        self._add_builtin_permission(self.role_no, Bioswale,
                                     'delete_bioswale')
        self._add_builtin_permission(self.role_no, MapFeaturePhoto,
                                     'delete_bioswalephoto')
        user_no = make_user(instance=self.instance,
                            make_role=lambda inst: self.role_no)
        self.assertFalse(photo.user_can_delete(user_no))


@override_settings(FEATURE_BACKEND_FUNCTION=None)
class PolygonalMapFeatureTest(OTMTestCase):
    def setUp(self):
        (x, y) = -76, 39
        self.point = self._make_point(x, y)
        self.polygon = self._make_square_polygon(x, y)

        self.polygon_area_sq_meters = 96101811.9499

        self.instance = make_instance(point=self.point, edge_length=1000000)
        self.user = make_commander_user(instance=self.instance)
        self.instance.add_map_feature_types(['Bioswale', 'RainGarden'])

        self.instance.annual_rainfall_inches = 30
        Bioswale.set_config_property(self.instance, 'diversion_rate', .5)
        Bioswale.set_config_property(self.instance, 'should_show_eco', True)

    def _make_point(self, x, y):
        point = Point(x, y, srid=4326)
        point.transform(3857)
        return point

    def _make_square_polygon(self, x, y):
        d = 0.1
        polygon = MultiPolygon(
            Polygon(
                ((x, y),
                 (x, y + d),
                 (x + d, y + d),
                 (x + d, y),
                 (x, y)), srid=4326),
            srid=4326)
        polygon.transform(3857)
        return polygon

    def _make_map_feature(self, MapFeatureClass, drainage_area=None,
                          geom=None, polygon=None):
        feature = MapFeatureClass(instance=self.instance,
                                  geom=(geom or self.point),
                                  polygon=(polygon or self.polygon),
                                  drainage_area=drainage_area)
        # Save the feature because area calculations make a query
        # that applies PostGIS functions to the saved polygon.
        feature.save_with_user(self.user)
        return feature

    @unittest.skip("Doesn't work and we don't use stormwater app")
    def test_calculate_area(self):
        bioswale = self._make_map_feature(Bioswale)
        self.assertAlmostEqual(bioswale.calculate_area(),
                               self.polygon_area_sq_meters, places=0)

    def assert_basis(self, basis, n_used, n_discarded):
        self.assertEqual(basis['resource']['n_objects_used'], n_used)
        self.assertEqual(basis['resource']['n_objects_discarded'], n_discarded)

    def _get_runoff_reduced(self, feature, expect_empty=False):
        benefits, basis, error = feature.benefits.benefits_for_object(
            self.instance, feature)

        self.assertIsNone(error)
        if expect_empty:
            self.assert_basis(basis, 0, 1)
            return 0
        else:
            self.assert_basis(basis, 1, 0)
            return benefits['resource']['stormwater']['value']

    def _assert_runoff_reduced(self, area_sq_meters, drainage_area_sq_meters,
                               diversion_rate, runoff_reduced):
        area = area_sq_meters * FEET_SQ_PER_METER_SQ
        drainage_area = drainage_area_sq_meters * FEET_SQ_PER_METER_SQ
        rainfall_ft = self.instance.annual_rainfall_inches * FEET_PER_INCH
        adjusted_area = area + (drainage_area * diversion_rate)
        expected = rainfall_ft * adjusted_area * GALLONS_PER_CUBIC_FT
        self.assertAlmostEqual(runoff_reduced, expected, places=0)

    @unittest.skip("Doesn't work and we don't use stormwater app")
    def test_rain_garden(self):
        RainGarden.set_config_property(self.instance, 'should_show_eco', True)
        drainage_area_sq_meters = 100000000.0
        feature = self._make_map_feature(RainGarden, drainage_area_sq_meters)
        runoff_reduced = self._get_runoff_reduced(feature)
        self._assert_runoff_reduced(
            self.polygon_area_sq_meters, drainage_area_sq_meters,
            .85, runoff_reduced)

    @unittest.skip("Doesn't work and we don't use stormwater app")
    def test_bioswale(self):
        drainage_area_sq_meters = 100000000.0
        feature = self._make_map_feature(Bioswale, drainage_area_sq_meters)
        runoff_reduced = self._get_runoff_reduced(feature)
        # Note Bioswale diversion rate set to .5 in setUp()
        self._assert_runoff_reduced(
            self.polygon_area_sq_meters, drainage_area_sq_meters,
            .5, runoff_reduced)

    def test_bioswale_no_drainage(self):
        feature = self._make_map_feature(Bioswale)
        runoff_reduced = self._get_runoff_reduced(feature, expect_empty=True)
        self.assertEqual(runoff_reduced, 0)

    def test_eco_not_wanted(self):
        RainGarden.set_config_property(self.instance, 'should_show_eco', False)
        drainage_area_sq_meters = 100000000.0
        feature = self._make_map_feature(RainGarden,
                                         drainage_area=drainage_area_sq_meters)
        runoff_reduced = self._get_runoff_reduced(feature, expect_empty=True)
        self.assertEqual(runoff_reduced, 0)

    @unittest.skip("Doesn't work and we don't use stormwater app")
    def test_bulk(self):
        drainage_area_sq_meters = 100000000.0
        # NOTE
        # Today, no check is made for overlapping stormwater resources.
        # In the future, either overlap should be invalid,
        # or the intersection should only be counted once in the total area.
        self._make_map_feature(Bioswale,
                               drainage_area=drainage_area_sq_meters)
        self._make_map_feature(Bioswale,
                               geom=self._make_point(-75.5, 39),
                               polygon=self._make_square_polygon(-75.5, 39),
                               drainage_area=drainage_area_sq_meters)

        benefits, basis = Bioswale.benefits.benefits_for_filter(
            self.instance, Filter('', '', self.instance))

        runoff_reduced = benefits['resource']['stormwater']['value']

        self.assert_basis(basis, 2, 0)
        self._assert_runoff_reduced(
            2 * self.polygon_area_sq_meters,
            2 * drainage_area_sq_meters,
            .5, runoff_reduced)

    @unittest.skip("Doesn't work and we don't use stormwater app")
    def test_bulk_partial_drainage_known(self):
        drainage_area_sq_meters = 100000000.0
        # NOTE
        # Today, no check is made for overlapping stormwater resources.
        # In the future, either overlap should be invalid,
        # or the intersection should only be counted once in the total area.
        self._make_map_feature(Bioswale,
                               drainage_area=drainage_area_sq_meters)
        self._make_map_feature(Bioswale,
                               geom=self._make_point(-75.5, 39),
                               polygon=self._make_square_polygon(-75.5, 39))

        benefits, basis = Bioswale.benefits.benefits_for_filter(
            self.instance, Filter('', '', self.instance))

        runoff_reduced = benefits['resource']['stormwater']['value']

        self.assert_basis(basis, 1, 1)
        self._assert_runoff_reduced(
            self.polygon_area_sq_meters,
            drainage_area_sq_meters,
            .5, runoff_reduced)

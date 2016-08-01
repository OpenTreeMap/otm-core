# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from treemap.ecobenefits import (FEET_SQ_PER_METER_SQ, FEET_PER_INCH,
                                 GALLONS_PER_CUBIC_FT)
from treemap.lib.udf import udf_create
from treemap.search import Filter
from treemap.tests.test_udfs import UdfCRUTestCase
from treemap.tests import (make_instance, make_commander_user)
from treemap.tests.base import OTMTestCase
from django.contrib.gis.geos import Point, Polygon, MultiPolygon
from django.test.utils import override_settings

from stormwater.models import Bioswale, RainGarden


@override_settings(FEATURE_BACKEND_FUNCTION=None)
class UdfGenericCreateTest(UdfCRUTestCase):
    def test_non_treemap_model(self):
        self.instance.map_feature_types += ['Bioswale']
        self.instance.save()

        body = {'udf.name': 'Testing choice',
                'udf.model': 'Bioswale',
                'udf.type': 'string'}

        udf_create(body, self.instance)


@override_settings(FEATURE_BACKEND_FUNCTION=None)
class PolygonalMapFeatureTest(OTMTestCase):
    def setUp(self):
        (x, y) = -76, 39
        self.point = Point(x, y, srid=4326)
        self.point.transform(3857)
        d = 0.1
        self.polygon = MultiPolygon(
            Polygon(
                ((x, y),
                 (x, y + d),
                 (x + d, y + d),
                 (x + d, y),
                 (x, y)), srid=4326),
            srid=4326)
        self.polygon.transform(3857)

        self.polygon_area_sq_meters = 96101811.9499

        self.instance = make_instance(point=self.point, edge_length=10000)
        self.user = make_commander_user(instance=self.instance)
        self.instance.add_map_feature_types(['Bioswale', 'RainGarden'])

        self.instance.annual_rainfall_inches = 30
        Bioswale.set_config_property(self.instance, 'diversion_rate', .5)
        Bioswale.set_config_property(self.instance, 'should_show_eco', True)

    def _make_map_feature(self, MapFeatureClass):
        feature = MapFeatureClass(instance=self.instance,
                                  geom=self.point,
                                  polygon=self.polygon)
        # Save the feature because area calculations make a query
        # that applies PostGIS functions to the saved polygon.
        feature.save_with_user(self.user)
        return feature

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
            return benefits['resource']['runoff_reduced']['value']

    def _assert_runoff_reduced(self, area_sq_meters, diversion_rate,
                               runoff_reduced):
        area = area_sq_meters * FEET_SQ_PER_METER_SQ
        rainfall_ft = self.instance.annual_rainfall_inches * FEET_PER_INCH
        expected = rainfall_ft * area * diversion_rate * GALLONS_PER_CUBIC_FT
        self.assertAlmostEqual(runoff_reduced, expected, places=0)

    def test_rain_garden(self):
        RainGarden.set_config_property(self.instance, 'should_show_eco', True)
        feature = self._make_map_feature(RainGarden)
        runoff_reduced = self._get_runoff_reduced(feature)
        self._assert_runoff_reduced(
            self.polygon_area_sq_meters, .95, runoff_reduced)

    def test_bioswale(self):
        feature = self._make_map_feature(Bioswale)
        runoff_reduced = self._get_runoff_reduced(feature)
        # Note Bioswale diversion rate set to .5 in setUp()
        self._assert_runoff_reduced(
            self.polygon_area_sq_meters, .5, runoff_reduced)

    def test_eco_not_wanted(self):
        RainGarden.set_config_property(self.instance, 'should_show_eco', False)
        feature = self._make_map_feature(RainGarden)
        runoff_reduced = self._get_runoff_reduced(feature, expect_empty=True)
        self.assertEqual(runoff_reduced, 0)

    def test_bulk(self):
        self._make_map_feature(Bioswale)
        self._make_map_feature(Bioswale)

        benefits, basis = Bioswale.benefits.benefits_for_filter(
            self.instance, Filter('', '', self.instance))

        runoff_reduced = benefits['resource']['runoff_reduced']['value']

        self.assert_basis(basis, 2, 0)
        self._assert_runoff_reduced(
            2 * self.polygon_area_sq_meters, .5, runoff_reduced)

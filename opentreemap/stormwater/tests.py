# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from treemap.lib.udf import udf_create
from treemap.tests.test_udfs import UdfCRUTestCase
from treemap.tests import (make_instance, make_commander_user)
from treemap.tests.base import OTMTestCase
from django.contrib.gis.geos import Point, Polygon, MultiPolygon
from django.test.utils import override_settings

from stormwater.models import Bioswale


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
    def test_calculate_area(self):
        (x, y) = -76, 39
        point = Point(x, y, srid=4326)
        point.transform(3857)
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
        expected_area_in_sq_meters = 96101812

        self.instance = make_instance(point=point, edge_length=10000)
        self.user = make_commander_user(instance=self.instance)
        self.instance.add_map_feature_types(['Bioswale'])
        self.bioswale = Bioswale(instance=self.instance,
                                 geom=point,
                                 polygon=polygon)
        # Save the feature because `calculate_area` makes a query
        # that applies PostGIS functions to the saved polygon.
        self.bioswale.save_with_user(self.user)
        self.assertAlmostEqual(self.bioswale.calculate_area(),
                               expected_area_in_sq_meters, places=0)

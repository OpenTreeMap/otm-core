# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.test.utils import override_settings

from manage_treemap.views.management import units
from treemap.tests import make_instance
from treemap.tests.base import OTMTestCase
from treemap.json_field import set_attr_on_json_field


# Enable green infrastructure (by disabling feature checks)
@override_settings(FEATURE_BACKEND_FUNCTION=None)
class UnitsTest(OTMTestCase):
    def setUp(self):
        pass

    def test_basic_specs(self):
        instance = make_instance(url_name='basic')
        specs = units(None, instance)

        self.assertIn('value_specs', specs)
        value_specs = specs['value_specs']
        self.assertEqual(len(value_specs), 4)

        s1, s2, s3, s4 = tuple(value_specs)

        self.assertEqual(s1.get('title'), 'Planting Site Fields')
        self.assertEqual(s2.get('title'), 'Tree Fields')
        self.assertEqual(s3.get('title'), 'Eco Benefits')
        self.assertEqual(s4.get('title'), 'Green Infrastructure')

        i1, i2, i3, i4 = \
            s1.get('items'), s2.get('items'), s3.get('items'), s4.get('items')

        self.assertEqual(len(i1), 2)
        self.assertEqual(len(i2), 3)
        self.assertEqual(len(i3), 5)
        self.assertEqual(len(i4), 2)

        self.assertEqual(i1[0].get('label'), 'Planting Site Width')
        self.assertEqual(i1[1].get('label'), 'Planting Site Length')

        self.assertEqual(i2[0].get('label'), 'Tree Diameter')
        self.assertEqual(i2[1].get('label'), 'Tree Height')
        self.assertEqual(i2[2].get('label'), 'Canopy Height')

        self.assertEqual(i3[0].get('label'), 'Energy conserved')
        self.assertEqual(i3[1].get('label'), 'Stormwater filtered')
        self.assertEqual(i3[2].get('label'), 'Air quality improved')
        self.assertEqual(i3[3].get('label'), 'Carbon dioxide removed')
        self.assertEqual(i3[4].get('label'), 'Carbon dioxide stored to date')

        self.assertEqual(i4[0].get('label'), 'Annual Rainfall')
        self.assertEqual(i4[1].get('label'), 'Area')

    def test_rain_barrel_specs(self):
        instance = make_instance(url_name='test-rainbarrel')
        instance.add_map_feature_types(['RainBarrel'])
        specs = units(None, instance)

        value_specs = specs.get('value_specs')
        self.assertEqual(len(value_specs), 5)

        rain_barrel_spec = value_specs[3]

        self.assertEqual(rain_barrel_spec.get('title'), 'Rain Barrel Fields')

        rain_barrel_items = rain_barrel_spec.get('items')

        self.assertEqual(len(rain_barrel_items), 1)
        self.assertEqual(rain_barrel_items[0].get('label'), 'Capacity')

    def test_water_barrel_specs(self):
        """
        Rename Rain Barrel to Water Barrel, and make sure that is
        what units returns.
        """
        instance = make_instance(url_name='test-waterbarrel')
        instance.add_map_feature_types(['RainBarrel'])
        set_attr_on_json_field(instance,
                               'config.terms.RainBarrel.singular',
                               'Water Barrel')
        specs = units(None, instance)

        value_specs = specs.get('value_specs')
        self.assertEqual(len(value_specs), 5)

        rain_barrel_spec = value_specs[3]

        self.assertEqual(rain_barrel_spec.get('title'), 'Water Barrel Fields')

    def test_rain_garden_specs(self):
        instance = make_instance(url_name='test-raingarden')
        instance.add_map_feature_types(['RainGarden'])

        specs = units(None, instance)

        value_specs = specs.get('value_specs')
        self.assertEqual(len(value_specs), 5)

        rain_barrel_spec = value_specs[3]

        self.assertEqual(rain_barrel_spec.get('title'), 'Rain Garden Fields')

        rain_barrel_items = rain_barrel_spec.get('items')

        self.assertEqual(len(rain_barrel_items), 1)
        self.assertEqual(rain_barrel_items[0].get('label'),
                         'Adjacent Drainage Area')

# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.test.utils import override_settings

from treemap.units import (is_convertible, is_formattable, get_display_value,
                           is_convertible_or_formattable, get_storage_value)
from treemap.models import Plot, Tree
from treemap.json_field import set_attr_on_json_field
from treemap.tests import make_instance, make_commander_user
from treemap.tests.base import OTMTestCase

UNIT_TEST_DISPLAY_DEFAULTS = {
    'test': {
        'unit_only': {'units': 'ft'},
        'digit_only': {'digits': 2},
        'both': {'units': 'ft', 'digits': 3},
        'separate_units': {'units': 'ft'}
    }
}
UNIT_TEST_STORAGE_UNITS = {
    'test': {
        'separate_units': 'in'
    }
}


@override_settings(DISPLAY_DEFAULTS=UNIT_TEST_DISPLAY_DEFAULTS,
                   STORAGE_UNITS=UNIT_TEST_STORAGE_UNITS)
class UnitConverterTest(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()

    def test_is_convertible_or_formatable(self):
        self.assertTrue(is_convertible_or_formattable('test', 'unit_only'))
        self.assertTrue(is_convertible_or_formattable('test', 'digit_only'))
        self.assertTrue(is_convertible_or_formattable('test', 'both'))
        self.assertTrue(
            is_convertible_or_formattable('test', 'separate_units'))
        self.assertFalse(is_convertible_or_formattable('test', 'random_field'))

    def test_is_convertible(self):
        self.assertTrue(is_convertible('test', 'unit_only'))
        self.assertFalse(is_convertible('test', 'digit_only'))
        self.assertTrue(is_convertible('test', 'both'))
        self.assertTrue(is_convertible('test', 'separate_units'))

    def test_is_formatable(self):
        self.assertFalse(is_formattable('test', 'unit_only'))
        self.assertTrue(is_formattable('test', 'digit_only'))
        self.assertTrue(is_formattable('test', 'both'))
        self.assertFalse(is_formattable('test', 'separate_units'))

    def test_get_display_value_unit_conversion(self):
        set_attr_on_json_field(
            self.instance, 'config.value_display.test.unit_only.units', 'in')
        val, display_val = get_display_value(
            self.instance, 'test', 'unit_only', 1)
        self.assertAlmostEqual(val, 12)
        self.assertEqual(display_val, '12,0')

    def test_get_display_value_no_unit_conversion_when_same_units(self):
        set_attr_on_json_field(
            self.instance, 'config.value_display.test.unit_only.units', 'ft')
        val, display_val = get_display_value(
            self.instance, 'test', 'unit_only', 1)
        self.assertEqual(val, 1)
        self.assertEqual(display_val, '1,0')

    def test_get_display_value_float_formatting(self):
        val, display_val = get_display_value(
            self.instance, 'test', 'digit_only', 1)
        self.assertEqual(val, 1)
        self.assertEqual(display_val, '1,00')

    def test_get_display_value_conversion(self):
        set_attr_on_json_field(
            self.instance, 'config.value_display.test.both.units', 'in')
        val, display_val = get_display_value(
            self.instance, 'test', 'both', 1)
        self.assertAlmostEqual(val, 12)
        self.assertEqual(display_val, '12,000')

    def test_get_storage_value(self):
        set_attr_on_json_field(
            self.instance, 'config.value_display.test.unit_only.units', 'in')
        self.assertAlmostEqual(1, get_storage_value(self.instance, 'test',
                                                    'unit_only', 12))

    def test_separate_storage_and_display_defaults(self):
        val, display_val = get_display_value(
            self.instance, 'test', 'separate_units', 12)
        self.assertEqual(val, 1)
        self.assertEqual(display_val, '1,0')


INTEGRATION_TEST_DISPLAY_DEFAULTS = {
    'plot': {
        'width': {'units': 'ft', 'digits': 2}
    },
    'tree': {
        'diameter': {'units': 'in', 'digits': 2},
    }
}


@override_settings(DISPLAY_DEFAULTS=INTEGRATION_TEST_DISPLAY_DEFAULTS)
class ConvertibleTest(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.user = make_commander_user(self.instance)
        self.plot = Plot(instance=self.instance, geom=self.instance.center)
        self.plot.save_with_user(self.user)
        self.tree = Tree(instance=self.instance, plot=self.plot)
        self.tree.save_with_user(self.user)

    def test_save_converts_width_when_units_differ(self):
        set_attr_on_json_field(
            self.instance, 'config.value_display.plot.width.units', 'in')
        self.plot.convert_to_display_units()
        self.plot.width = 12
        self.plot.convert_to_database_units()
        self.plot.save_with_user(self.user)

        updated_plot = Plot.objects.get(pk=self.plot.pk)
        self.assertAlmostEqual(1, updated_plot.width)

    def test_save_converts_diameter_when_units_differ(self):
        set_attr_on_json_field(
            self.instance, 'config.value_display.tree.diameter.units', 'ft')
        self.tree.convert_to_display_units()
        self.tree.diameter = 1
        self.tree.convert_to_database_units()
        self.tree.save_with_user(self.user)

        updated_tree = Tree.objects.get(pk=self.tree.pk)
        self.assertAlmostEqual(12, updated_tree.diameter)

    def test_save_does_not_convert_width_when_units_same(self):
        set_attr_on_json_field(
            self.instance, 'config.value_display.plot.width.units', 'ft')
        self.plot.width = 12
        self.plot.save_with_user(self.user)

        updated_plot = Plot.objects.get(pk=self.plot.pk)
        self.assertEqual(12, updated_plot.width)

    def test_save_does_not_convert_diameter_when_units_same(self):
        set_attr_on_json_field(
            self.instance, 'config.value_display.tree.diameter.units', 'in')
        self.tree.diameter = 1
        self.tree.save_with_user(self.user)

        updated_tree = Tree.objects.get(pk=self.tree.pk)
        self.assertEqual(1, updated_tree.diameter)

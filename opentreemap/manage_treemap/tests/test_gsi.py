# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json

from django.core.exceptions import ValidationError
from django.test.utils import override_settings

from manage_treemap.views.green_infrastructure import green_infrastructure
from opentreemap.util import dotted_split
from stormwater.models import Bioswale
from treemap.audit import (FieldPermission)
from treemap.instance import Instance
from treemap.tests import (make_instance, make_commander_user, make_request,
                           make_commander_role)
from treemap.tests.base import OTMTestCase
from treemap.units import get_value_display_attr


@override_settings(FEATURE_BACKEND_FUNCTION=None)
class AddMapFeatureTypeTest(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()

    def test_exception_adding_duplicate(self):
        self.assertRaises(ValidationError, self.instance.add_map_feature_types,
                          ['Plot'])

    def test_exception_adding_nonexistent(self):
        self.assertRaises(ValidationError, self.instance.add_map_feature_types,
                          ['IDoNotExist'])

    def test_type_and_permissions_are_added(self):
        role = make_commander_role(self.instance)
        current_map_feature_types = set(self.instance.map_feature_types)
        self.instance.add_map_feature_types(['RainGarden'])
        instance = Instance.objects.get(pk=self.instance.pk)
        self.assertEqual(set(instance.map_feature_types),
                         current_map_feature_types | {'RainGarden'})
        qs = FieldPermission.objects.filter(
            instance=instance, model_name='RainGarden',
            field_name='drainage_area', role=role)
        self.assertEqual(len(qs), 1)


@override_settings(FEATURE_BACKEND_FUNCTION=None)
class GreenInfrastructureUpdateTest(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.commander = make_commander_user(self.instance)

    def tearDown(self):
        self.instance.remove_map_feature_types(keep=['Plot'])

    def _activate(self, mft):
        already_activated = self.instance.map_feature_types
        if mft not in already_activated:
            self.instance.add_map_feature_types([mft])

    def test_add_map_feature_types(self):
        mft = 'Bioswale'
        key = 'map_feature_types'
        updates = {
            'instance.config.{}.{}'.format(key, mft): True
        }

        json_updates = json.dumps(updates)
        request = make_request(method='PUT',
                               body=json_updates,
                               user=self.commander)

        green_infrastructure(request, self.instance)

        map_feature_types = self.instance.config.get(key)
        self.assertGreater(len(map_feature_types), 0)
        self.assertIn(mft, map_feature_types)

    def test_remove_map_feature_types(self):
        mft = 'Bioswale'
        key = 'map_feature_types'
        request_key = 'instance.config.{}.{}'.format(key, mft)
        updates = {request_key: True}

        json_updates = json.dumps(updates)
        request = make_request(method='PUT',
                               body=json_updates,
                               user=self.commander)

        green_infrastructure(request, self.instance)

        updates[request_key] = False

        json_updates = json.dumps(updates)
        request = make_request(method='PUT',
                               body=json_updates,
                               user=self.commander)

        green_infrastructure(request, self.instance)
        map_feature_types = self.instance.config.get(key)
        self.assertNotIn(mft, map_feature_types)

    def test_map_feature_applicable_constant_validation(self):
        self._activate('Bioswale')

        request_key = 'instance.config.map_feature_config.Bioswale'\
                      '.diversion_rate'
        updates = {request_key: 'x'}
        json_updates = json.dumps(updates)
        request = make_request(method='PUT',
                               body=json_updates,
                               user=self.commander)

        with self.assertRaises(ValidationError):
            green_infrastructure(request, self.instance)

        updates = {request_key: -.166}
        json_updates = json.dumps(updates)
        request = make_request(method='PUT',
                               body=json_updates,
                               user=self.commander)

        with self.assertRaises(ValidationError):
            green_infrastructure(request, self.instance)

        updates = {request_key: 1.66}
        json_updates = json.dumps(updates)
        request = make_request(method='PUT',
                               body=json_updates,
                               user=self.commander)

        with self.assertRaises(ValidationError):
            green_infrastructure(request, self.instance)

        updates = {request_key: .166}
        json_updates = json.dumps(updates)
        request = make_request(method='PUT',
                               body=json_updates,
                               user=self.commander)

        green_infrastructure(request, self.instance)

        bioswale_config = Bioswale.get_config(self.instance)
        self.assertEqual(bioswale_config.get('diversion_rate', None), 0.166)

    def test_map_feature_inapplicable_config_validation(self):
        self._activate('RainBarrel')
        request_key = 'instance.config.map_feature_config.RainBarrel'\
                      '.should_show_eco'
        updates = {request_key: True}
        json_updates = json.dumps(updates)
        request = make_request(method='PUT',
                               body=json_updates,
                               user=self.commander)

        with self.assertRaises(ValidationError):
            green_infrastructure(request, self.instance)

    def test_show_eco_without_rainfall(self):
        self._activate('Bioswale')
        self.assertIsNone(self.instance.annual_rainfall_inches)
        Bioswale.set_config_property(self.instance, 'diversion_rate', .9)

        request_key = 'instance.config.map_feature_config.Bioswale'\
                      '.should_show_eco'
        updates = {request_key: True}
        json_updates = json.dumps(updates)
        request = make_request(method='PUT',
                               body=json_updates,
                               user=self.commander)

        with self.assertRaises(ValidationError):
            green_infrastructure(request, self.instance)

    def test_show_eco_without_constant(self):
        self._activate('Bioswale')
        self.instance.annual_rainfall_inches = 8.0
        Bioswale.set_config_property(self.instance, 'diversion_rate', None)

        request_key = 'instance.config.map_feature_config.Bioswale'\
                      '.should_show_eco'
        updates = {request_key: True}
        json_updates = json.dumps(updates)
        request = make_request(method='PUT',
                               body=json_updates,
                               user=self.commander)

        with self.assertRaises(ValidationError):
            green_infrastructure(request, self.instance)

    def test_annual_rainfall_config_validation(self):
        request_key = 'instance.config.annual_rainfall_inches'
        updates = {request_key: 'x'}
        json_updates = json.dumps(updates)
        request = make_request(method='PUT',
                               body=json_updates,
                               user=self.commander)

        with self.assertRaises(ValidationError):
            green_infrastructure(request, self.instance)

        updates[request_key] = '-10'
        json_updates = json.dumps(updates)
        request = make_request(method='PUT',
                               body=json_updates,
                               user=self.commander)

        with self.assertRaises(ValidationError):
            green_infrastructure(request, self.instance)

        updates[request_key] = '10'
        json_updates = json.dumps(updates)
        request = make_request(method='PUT',
                               body=json_updates,
                               user=self.commander)

        green_infrastructure(request, self.instance)

        self.assertEqual(self.instance.annual_rainfall_inches, 10.0)

    def test_annual_rainfall_unit_conversion(self):
        rainfall_unit_key, rainfall_unit = get_value_display_attr(
            self.instance, 'greenInfrastructure', 'rainfall', 'units')
        self.assertEqual(rainfall_unit, 'in')
        __, __, unit_key = dotted_split(rainfall_unit_key, 3, maxsplit=2)

        self.assertEqual(rainfall_unit, 'in')

        config_key = 'annual_rainfall_inches'
        request_key = 'instance.config.annual_rainfall_inches'
        updates = {request_key: 10}
        json_updates = json.dumps(updates)
        request = make_request(method='PUT',
                               body=json_updates,
                               user=self.commander)

        green_infrastructure(request, self.instance)

        self.assertEqual(self.instance.config[config_key], 10.0)

        self.instance.config[unit_key] = 'cm'

        config_key = 'annual_rainfall_inches'
        request_key = 'instance.config.{}'.format(config_key)
        updates = {request_key: 25.4}
        json_updates = json.dumps(updates)
        request = make_request(method='PUT',
                               body=json_updates,
                               user=self.commander)

        green_infrastructure(request, self.instance)

        self.assertEqual(self.instance.config[config_key], 10.0)

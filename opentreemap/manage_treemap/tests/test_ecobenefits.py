# -*- coding: utf-8 -*-
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json

from django.core.exceptions import ValidationError

from manage_treemap.views.management import update_benefits

from treemap.instance import Instance
from treemap.models import BenefitCurrencyConversion
from treemap.tests import make_instance, make_commander_user, make_request
from treemap.tests.base import OTMTestCase


class BenefitsUpdateTest(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.conversions =\
            BenefitCurrencyConversion.get_default_for_region('PiedmtCLT')
        self.conversions.save()

        self.instance.eco_benefits_conversion = self.conversions
        self.instance.save()
        self.commander = make_commander_user(self.instance)

    def test_update_some_values(self):
        updates = {
            'benefitCurrencyConversion.currency_symbol': '$',
            'benefitCurrencyConversion.electricity_kwh_to_currency': '1.0',
            'benefitCurrencyConversion.natural_gas_kbtu_to_currency': '2.0',
            'benefitCurrencyConversion.h20_gal_to_currency': '3.0',
            'benefitCurrencyConversion.co2_lb_to_currency': '4.0',
            'benefitCurrencyConversion.o3_lb_to_currency': '5.0',
            'benefitCurrencyConversion.nox_lb_to_currency': '6.0',
            'benefitCurrencyConversion.pm10_lb_to_currency': '7.0',
            'benefitCurrencyConversion.sox_lb_to_currency': '8.0',
            'benefitCurrencyConversion.voc_lb_to_currency': '9.0',
        }

        json_updates = json.dumps(updates)
        request = make_request(method='PUT',
                               body=json_updates,
                               user=self.commander)

        update_benefits(request, self.instance)

        conv = self.instance.eco_benefits_conversion
        self.assertEqual(conv.currency_symbol, '$')
        self.assertEqual(conv.electricity_kwh_to_currency, 1.0)
        self.assertEqual(conv.natural_gas_kbtu_to_currency, 2.0)
        self.assertEqual(conv.h20_gal_to_currency, 3.0)
        self.assertEqual(conv.co2_lb_to_currency, 4.0)
        self.assertEqual(conv.o3_lb_to_currency, 5.0)
        self.assertEqual(conv.nox_lb_to_currency, 6.0)
        self.assertEqual(conv.pm10_lb_to_currency, 7.0)
        self.assertEqual(conv.sox_lb_to_currency, 8.)
        self.assertEqual(conv.voc_lb_to_currency, 9.0)

    def test_error_on_blank(self):
        updates = {
            'benefitCurrencyConversion.currency_symbol': '$',
            'benefitCurrencyConversion.electricity_kwh_to_currency': '',
            'benefitCurrencyConversion.natural_gas_kbtu_to_currency': '2.0',
            'benefitCurrencyConversion.h20_gal_to_currency': '3.0',
            'benefitCurrencyConversion.co2_lb_to_currency': '4.0',
            'benefitCurrencyConversion.o3_lb_to_currency': '5.0',
            'benefitCurrencyConversion.nox_lb_to_currency': '6.0',
            'benefitCurrencyConversion.pm10_lb_to_currency': '7.0',
            'benefitCurrencyConversion.sox_lb_to_currency': '8.0',
            'benefitCurrencyConversion.voc_lb_to_currency': '9.0',
        }

        json_updates = json.dumps(updates)
        request = make_request(method='PUT',
                               body=json_updates,
                               user=self.commander)

        with self.assertRaises(ValidationError):
            update_benefits(request, self.instance)

        updated_instance = Instance.objects.get(pk=self.instance.pk)
        self.assertEqual(updated_instance.eco_benefits_conversion,
                         self.conversions)

    def test_error_on_negative(self):
        updates = {
            'benefitCurrencyConversion.currency_symbol': '$',
            'benefitCurrencyConversion.electricity_kwh_to_currency': '1.0',
            'benefitCurrencyConversion.natural_gas_kbtu_to_currency': '2.0',
            'benefitCurrencyConversion.h20_gal_to_currency': '3.0',
            'benefitCurrencyConversion.co2_lb_to_currency': '-4.0',
            'benefitCurrencyConversion.o3_lb_to_currency': '5.0',
            'benefitCurrencyConversion.nox_lb_to_currency': '6.0',
            'benefitCurrencyConversion.pm10_lb_to_currency': '7.0',
            'benefitCurrencyConversion.sox_lb_to_currency': '8.0',
            'benefitCurrencyConversion.voc_lb_to_currency': '9.0',
        }

        json_updates = json.dumps(updates)
        request = make_request(method='PUT',
                               body=json_updates,
                               user=self.commander)

        with self.assertRaises(ValidationError):
            update_benefits(request, self.instance)

        updated_instance = Instance.objects.get(pk=self.instance.pk)
        self.assertEqual(updated_instance.eco_benefits_conversion,
                         self.conversions)

    def test_error_on_non_number(self):
        updates = {
            'benefitCurrencyConversion.currency_symbol': '$',
            'benefitCurrencyConversion.electricity_kwh_to_currency': '1.0',
            'benefitCurrencyConversion.natural_gas_kbtu_to_currency': '2.0',
            'benefitCurrencyConversion.h20_gal_to_currency': '3.0',
            'benefitCurrencyConversion.co2_lb_to_currency': '4.0',
            'benefitCurrencyConversion.o3_lb_to_currency': '5.0',
            'benefitCurrencyConversion.nox_lb_to_currency': '6.0',
            'benefitCurrencyConversion.pm10_lb_to_currency': 'Seven',
            'benefitCurrencyConversion.sox_lb_to_currency': '8.0',
            'benefitCurrencyConversion.voc_lb_to_currency': '9.0',
        }

        json_updates = json.dumps(updates)
        request = make_request(method='PUT',
                               body=json_updates,
                               user=self.commander)

        with self.assertRaises(ValidationError):
            update_benefits(request, self.instance)

        updated_instance = Instance.objects.get(pk=self.instance.pk)
        self.assertEqual(updated_instance.eco_benefits_conversion,
                         self.conversions)

# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import locale

from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.utils.translation import ugettext as _

from opentreemap.util import json_from_request, dotted_split
from otm_comments.views import get_comments
from treemap.models import BenefitCurrencyConversion
from treemap.util import package_field_errors
from treemap.views.photo import get_photos


def management_root(request, instance_url_name):
    return redirect('site_config', instance_url_name=instance_url_name)


def admin_counts(request, instance):
    humanize = lambda n: '' if n == 0 else n if n < 100 else '99+'

    comment_count = get_comments({}, instance).count()
    photo_count = get_photos(instance).count()
    udf_notifications = instance.config.get('udf_notifications', [])

    return {
        'admin_notifications': {
            'comments': humanize(comment_count),
            'photos': humanize(photo_count),
            'community': humanize(photo_count + comment_count),
            'udfs': humanize(len(udf_notifications))
        },
        'udf_notifications': udf_notifications
    }


def benefits_convs(request, instance):
    conv = instance.eco_benefits_conversion or _get_default_conversions()

    field_groups = {
        _('Energy Factors'): {
            _('per kWh of electricity'):
            'benefitCurrencyConversion.electricity_kwh_to_currency',
            _('per kBTU of natural gas'):
            'benefitCurrencyConversion.natural_gas_kbtu_to_currency',
        },
        _('Stormwater Factors'): {
            _('per gallon of stormwater reduced'):
            'benefitCurrencyConversion.h20_gal_to_currency',
        },
        _('CO₂ Factors'): {
            _('per lb of CO₂'):
            'benefitCurrencyConversion.co2_lb_to_currency',
        },
        _('Air Quality Factors'): {
            _('per lb of O₃'):
            'benefitCurrencyConversion.o3_lb_to_currency',
            _('per lb of NOₓ'):
            'benefitCurrencyConversion.nox_lb_to_currency',
            _('per lb of PM10'):
            'benefitCurrencyConversion.pm10_lb_to_currency',
            _('per lb of SOₓ'):
            'benefitCurrencyConversion.sox_lb_to_currency',
            _('per lb of VOC'):
            'benefitCurrencyConversion.voc_lb_to_currency'
        }
    }

    pfx = ('<span class="currency-value">' +
           conv.currency_symbol + '</span> ')

    for group_title, fields in field_groups.iteritems():
        fields_with_pfx = [((pfx + label), value)
                           for label, value in fields.iteritems()]
        field_groups[group_title] = fields_with_pfx

    return {'benefitCurrencyConversion': conv,
            'benefit_fields': field_groups}


def update_benefits(request, instance):
    conv = instance.eco_benefits_conversion or _get_default_conversions()

    valid_fields = ('currency_symbol',
                    'electricity_kwh_to_currency',
                    'natural_gas_kbtu_to_currency',
                    'h20_gal_to_currency',
                    'co2_lb_to_currency',
                    'o3_lb_to_currency',
                    'nox_lb_to_currency',
                    'pm10_lb_to_currency',
                    'sox_lb_to_currency',
                    'voc_lb_to_currency')

    valid_fields = ["benefitCurrencyConversion." + field
                    for field in valid_fields]

    updated_values = json_from_request(request)

    for field, value in updated_values.iteritems():
        if field in valid_fields:
            field_part = dotted_split(field, 2)[1]
            setattr(conv, field_part, value)
        else:
            raise Exception(
                'invalid field specified %s for benefit conversion' % field)

    try:
        conv.save()
    except ValidationError as e:
        raise ValidationError(
            package_field_errors('benefitCurrencyConversion', e))

    instance.eco_benefits_conversion = conv
    instance.update_eco_rev()
    instance.save()

    return {'ok': True}


def _get_default_conversions():
    currency_symbol = locale.localeconv()['currency_symbol'] or '$'
    return BenefitCurrencyConversion(currency_symbol=currency_symbol)

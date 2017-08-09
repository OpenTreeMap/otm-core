# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import re

from django.db import connection
from django.utils.translation import ugettext as _
from django.utils.formats import number_format

from treemap.units import get_units, get_display_value

COLOR_RE = re.compile(r'^(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')


def format_benefits(instance, benefits, basis, digits=None):
    # keep the top level module dependencies small
    from treemap.ecobenefits import BenefitCategory

    currency_symbol = ''
    if instance.eco_benefits_conversion:
        currency_symbol = instance.eco_benefits_conversion.currency_symbol

    # FYI: this mutates the underlying benefit dictionaries
    total_currency = 0
    for benefit_group in benefits.values():
        for key, benefit in benefit_group.iteritems():
            if benefit['currency'] is not None:
                # TODO: Use i18n/l10n to format currency
                benefit['currency_saved'] = currency_symbol + number_format(
                    benefit['currency'], decimal_pos=0)
                if BenefitCategory.is_annual_table.get(key, True):
                    total_currency += benefit['currency']

            unit_key = benefit.get('unit-name')

            if unit_key:
                __, value = get_display_value(
                    instance, unit_key, key, benefit['value'], digits)

                benefit['name'] = key
                benefit['value'] = value
                benefit['unit'] = get_units(instance, unit_key, key)

    benefits['all'] = {'totals': {
        'value': None,
        'label': _('Total annual benefits'),
        'currency': total_currency,
        'currency_saved': currency_symbol + number_format(
            total_currency, decimal_pos=0)}}

    # Add total and percent to basis
    rslt = {'benefits': benefits,
            'benefits_total_currency': total_currency,
            'currency_symbol': currency_symbol,
            'basis': basis}

    return rslt


def get_function_by_path(fn_path):
    fn_paths = fn_path.split('.')
    modulepath = '.'.join(fn_paths[:-1])
    fcn = fn_paths[-1]
    mod = __import__(modulepath, fromlist=[fcn])

    return getattr(mod, fcn)


def execute_sql(sql):
    cursor = connection.cursor()
    try:
        cursor.execute(sql)
    finally:
        cursor.close()

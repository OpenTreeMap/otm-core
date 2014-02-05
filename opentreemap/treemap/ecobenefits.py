# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.db import DEFAULT_DB_ALIAS
from django.utils.translation import ugettext_lazy as trans
from django.shortcuts import get_object_or_404
from django.contrib.gis.geos.point import Point

from treemap import ecobackend
from treemap.models import Tree
from treemap.decorators import json_api_call
from treemap.models import ITreeRegion


WATTS_PER_BTU = 0.29307107
GAL_PER_CUBIC_M = 264.172052
LBS_PER_KG = 2.20462


def benefits_for_trees(trees, instance):
    # This code may need to be reworked for django 1.6.x
    # the eco benefit service expects a fully formed
    # sql 'where' clause. We can compile that directly
    # from the django query
    query = trees.query
    compiler = query.get_compiler(DEFAULT_DB_ALIAS)
    query.where.as_sql(qn=compiler.quote_name_unless_alias,
                       connection=compiler.connection)
    where, where_params = query.where.as_sql(
        qn=compiler.quote_name_unless_alias, connection=compiler.connection)

    # Need to replace %s query params with postgres placeholders
    # $1, $2, etc
    idx = 1
    i = 0
    whereWithDollars = ''
    while i < len(where) - 1:
        char = where[i]

        if char == '%' and where[i + 1] == 's':
            whereWithDollars += '$%d' % idx
            idx += 1
            i += 1
        else:
            whereWithDollars += char

        i += 1

    whereWithDollars += where[-1]

    params = (('where', whereWithDollars), ('instance_id', instance.pk))
    params += tuple([("param", p) for p in where_params])

    rawb, err = ecobackend.json_benefits_call(
        'eco_summary.json', params, post=True)

    if err:
        raise Exception(err)

    benefits = rawb['Benefits']

    return _compute_currency_and_transform_units(instance, benefits)


def _compute_currency_and_transform_units(instance, benefits):
    if 'n_trees' in benefits:
        ntrees = int(benefits['n_trees'])
    else:
        ntrees = 1

    hydrofactors = ['hydro_interception']

    aqfactors = ['aq_ozone_dep', 'aq_nox_dep', 'aq_nox_avoided',
                 'aq_pm10_dep', 'aq_sox_dep', 'aq_sox_avoided',
                 'aq_voc_avoided', 'aq_pm10_avoided', 'bvoc']

    co2factors = ['co2_sequestered', 'co2_avoided']
    co2storagefactors = ['co2_storage']

    energyfactor = ['natural_gas', 'electricity']

    # TODO:
    # eco.py converts from kg -> lbs to use the
    # itree defaults currency conversions but it looks like
    # we are pulling from the speadsheets are in kgs... we
    # need to verify units
    groups = {
        'airquality': ('lbs/year', aqfactors),
        'co2': ('lbs/year', co2factors),
        'co2storage': ('lbs', co2storagefactors),
        'stormwater': ('gal', hydrofactors),
        'energy': ('kwh', energyfactor)
    }

    # currency conversions are in lbs, so do this calc first
    # same with hydro
    for benefit in aqfactors + co2factors:
        benefits[benefit] *= LBS_PER_KG

    benefits['hydro_interception'] *= GAL_PER_CUBIC_M

    factor_conversions = instance.factor_conversions

    for benefit in benefits:
        value = benefits[benefit]

        if factor_conversions and value and benefit in factor_conversions:
            currency = factor_conversions[benefit] * value
        else:
            currency = 0.0

        benefits[benefit] = (value, currency)

    # currency conversions are in kbtus, so do this after
    # currency conversion
    nat_gas_kbtu, nat_gas_cur = benefits['natural_gas']
    nat_gas_kwh = nat_gas_kbtu * WATTS_PER_BTU
    benefits['natural_gas'] = (nat_gas_kwh, nat_gas_cur)

    rslt = {}

    for group, (unit, keys) in groups.iteritems():
        valuetotal = currencytotal = 0

        for key in keys:
            value, currency = benefits.get(key, (0, 0))

            valuetotal += value
            currencytotal += currency

        if currencytotal == 0:
            currencytotal = None

        rslt[group] = {'value': valuetotal,
                       'currency': currencytotal,
                       'unit': unit}

    return (rslt, ntrees)


def tree_benefits(instance, tree_or_tree_id):
    """Given a tree id, determine eco benefits via eco.py"""

    if isinstance(tree_or_tree_id, int):
        InstanceTree = instance.scope_model(Tree)
        tree = get_object_or_404(InstanceTree, pk=tree_or_tree_id)
    else:
        tree = tree_or_tree_id

    if not tree.diameter:
        rslt = {'benefits': {}, 'error': 'MISSING_DBH'}
    elif not tree.species:
        rslt = {'benefits': {}, 'error': 'MISSING_SPECIES'}
    else:
        if instance.itree_region_default:
            region = instance.itree_region_default
        else:
            regions = ITreeRegion.objects\
                                 .filter(geometry__contains=tree.plot.geom)

            if len(regions) > 0:
                region = regions[0].code
            else:
                region = None

        if region:
            params = {'otmcode': tree.species.otm_code,
                      'diameter': tree.diameter,
                      'region': region,
                      'instanceid': instance.pk,
                      'speciesid': tree.species.pk}

            rawb, err = ecobackend.json_benefits_call(
                'eco.json', params.iteritems())

            if err:
                rslt = {'error': err}
            else:
                benefits, _ = _compute_currency_and_transform_units(
                    instance, rawb['Benefits'])

                rslt = {'benefits': benefits}
        else:
            rslt = {'benefits': {}, 'error': 'MISSING_REGION'}

    return rslt


def within_itree_regions(request):
    x = request.GET.get('x', None)
    y = request.GET.get('y', None)
    return (bool(x) and bool(y) and
            ITreeRegion.objects
            .filter(geometry__contains=Point(float(x),
                                             float(y))).exists())

_benefit_labels = {
    # Translators: 'Energy' is the name of an eco benefit
    'energy':     trans('Energy'),
    # Translators: 'Stormwater' is the name of an eco benefit
    'stormwater': trans('Stormwater'),
    # Translators: 'Carbon Dioxide' is the name of an eco benefit
    'co2':        trans('Carbon Dioxide'),
    # Translators: 'Carbon Dioxide Stored' is the name of an eco benefit
    'co2storage': trans('Carbon Dioxide Stored'),
    # Translators: 'Air Quality' is the name of an eco benefit
    'airquality': trans('Air Quality')
}


def get_benefit_label(benefit_name):
    return _benefit_labels[benefit_name]


within_itree_regions_view = json_api_call(within_itree_regions)

# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.utils.translation import ugettext_lazy as _
from django.contrib.gis.geos.point import Point
from django.db import connection

from django_tinsel.decorators import json_api_call
import itertools

from treemap import ecobackend
from treemap.ecocache import get_cached_benefits

WATTS_PER_BTU = 0.29307107
GAL_PER_CUBIC_M = 264.172052
LBS_PER_KG = 2.20462
FEET_SQ_PER_METER_SQ = 10.7639
FEET_PER_INCH = 1/12.0
GALLONS_PER_CUBIC_FT = 7.48


class BenefitCategory(object):
    ENERGY = 'energy'
    STORMWATER = 'stormwater'
    AIRQUALITY = 'airquality'
    CO2 = 'co2'
    CO2STORAGE = 'co2storage'

    GROUPS = (ENERGY, STORMWATER, AIRQUALITY, CO2, CO2STORAGE)

    is_annual_table = {
        ENERGY: True,
        STORMWATER: True,
        AIRQUALITY: True,
        CO2: True,
        CO2STORAGE: False
    }


class BenefitCalculator(object):
    """
    Compute benefit for a given set of filtered objects

    Both of these methods return a dictionary that looks like:
    { group-name:
       { name-of-benefit:
          { 'value': benefit-value,
            'currency': monetary-savings,
            'unit': units-for-this-value,
            'label': label-to-show-for-this-unit,
            'unit-name': lookup-value-for-unit
          },
          ...
       },
       ...
    }

    When all benefits are run, any benefit with the same group-name and
    name-of-benefit will be merged (value and currency added together).
    In addition, values in a given group will be shown together.

    lookup-value-for-unit is used to format the units for display and
    is optional.

    The basis dictionary provides info about what went into
    the calculation. It has the following schema:
    { name-of-group:
      { 'n_objects_used': ...
        'n_objects_discarded': ...
      },
      ...
    }

    You may add additional keys to basis groups however, note
    that basis groups are summed across all eco benefits returned
    so your additional keys should be numbers

    benefits_for_filter returns a tuple:
    (dict from above, basis dict)

    benefits_for_object returns a tuple of:
    (dict from above, basis dict, error [or None])
    """

    def benefits_for_filter(self, instance, item_filter):
        return {}

    def benefits_for_object(self, instance, obj):
        return {}


class CountOnlyBenefitCalculator(BenefitCalculator):
    def __init__(self, clz):
        self.clz = clz

    def benefits_for_filter(self, instance, item_filter):
        features = item_filter.get_objects(self.clz)
        return ({},
                {'resource':
                 {'n_objects_used': 0,
                  'n_objects_discarded': features.count()}})

    def benefits_for_object(self, instance, obj):
        return {}, {}, None


class TreeBenefitsCalculator(BenefitCalculator):
    def _make_sql_from_query(self, query):
        sql, params = query.sql_with_params()
        cursor = connection.cursor()
        # Returning a unicode SQL string ensures that any string
        # replacements done to query string will not raise
        # UnicodeDecodeError
        return unicode(cursor.mogrify(sql, params), 'utf-8')

    def benefits_for_filter(self, instance, item_filter):
        from treemap.models import Plot, Tree

        instance = item_filter.instance
        plots = item_filter.get_objects(Plot)
        trees = Tree.objects.filter(plot__in=plots)
        n_total_trees = trees.count()

        if not instance.has_itree_region():
            basis = {'plot':
                     {'n_objects_used': 0,
                      'n_objects_discarded': n_total_trees}}
            return ({}, basis)

        if n_total_trees == 0:
            basis = {'plot':
                     {'n_objects_used': 0,
                      'n_objects_discarded': n_total_trees}}
            empty_rslt = compute_currency_and_transform_units(
                instance, {})
            return (empty_rslt, basis)

        # When calculating benefits we can skip region information
        # if there is only one intersecting region or if the
        # instance forces a region on us
        regions = instance.itree_regions()
        if len(regions) == 1:
            region_code = regions[0].code
        else:
            region_code = None

        # We want to do a values query that returns the info that
        # we need for an eco calculation:
        # diameter, species id and species code
        #
        # The species id is used to find potential overrides
        values = ('diameter',
                  'species__pk',
                  'species__otm_code',)

        # If there isn't a single region we need to
        # include geometry information
        if not region_code:
            values += ('plot__geom',)

        # We use two extra instance filter to help out
        # the database a bit when doing the joins
        treeValues = trees.filter(species__isnull=False)\
                          .filter(diameter__isnull=False)\
                          .filter(plot__instance=instance)\
                          .filter(species__instance=instance)\
                          .values_list(*values)

        query = self._make_sql_from_query(treeValues.query)

        # We want to extract x and y coordinates but django
        # doesn't make this easy since we need to force a join
        # on plot/mapfeature. To make sure the djago machinery
        # does that we use "plot__geom" above and then
        # do this rather dubious string manipulation below
        if not region_code:
            targetGeomField = '"treemap_mapfeature"."the_geom_webmercator"'
            xyGeomFields = 'ST_X(%s), ST_Y(%s)' % \
                           (targetGeomField, targetGeomField)

            query = query.replace(targetGeomField, xyGeomFields, 1)

        params = {'query': query,
                  'instance_id': instance.pk,
                  'region': region_code or ""}

        rawb, err = ecobackend.json_benefits_call(
            'eco_summary.json', params.iteritems(), post=True)

        if err:
            raise Exception(err)

        benefits = rawb['Benefits']

        if 'n_trees' in benefits:
            n_computed_trees = int(benefits['n_trees'])
        else:
            n_computed_trees = 1

        # Extrapolate an average over the rest of the urban forest
        if n_computed_trees > 0 and n_total_trees > 0:
            percent = float(n_computed_trees) / n_total_trees
            for key in benefits:
                benefits[key] /= percent

        rslt = compute_currency_and_transform_units(instance, benefits)

        basis = {'plot':
                 {'n_objects_used': n_computed_trees,
                  'n_objects_discarded': n_total_trees - n_computed_trees}}

        return (rslt, basis)

    def benefits_for_object(self, instance, plot):
        tree = plot.current_tree()
        error = None

        if tree is None:
            rslt = None
            error = 'NO_TREE'
        elif not tree.diameter:
            rslt = None
            error = 'MISSING_DBH'
        elif not tree.species:
            rslt = None
            error = 'MISSING_SPECIES'
        else:
            region_code = plot.itree_region.code

            if region_code:
                params = {'otmcode': tree.species.otm_code,
                          'diameter': tree.diameter,
                          'region': region_code,
                          'instanceid': instance.pk,
                          'speciesid': tree.species.pk}

                rawb, err = ecobackend.json_benefits_call(
                    'eco.json', params.iteritems())

                if err:
                    rslt = {'error': err}
                    error = err
                else:
                    benefits = compute_currency_and_transform_units(
                        instance, rawb['Benefits'])

                    rslt = benefits
            else:
                rslt = None
                error = 'MISSING_REGION'

        basis = {'plot':
                 {'n_objects_used': 1 if rslt else 0,
                  'n_objects_discarded': 0 if rslt else 1}}

        return (rslt, basis, error)


def compute_currency_and_transform_units(instance, benefits):

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
        BenefitCategory.AIRQUALITY: ('lbs', aqfactors),
        BenefitCategory.CO2: ('lbs', co2factors),
        BenefitCategory.CO2STORAGE: ('lbs', co2storagefactors),
        BenefitCategory.STORMWATER: ('gal', hydrofactors),
        BenefitCategory.ENERGY: ('kwh', energyfactor)
    }

    # currency conversions are in lbs, so do this calc first
    # same with hydro
    for benefit in aqfactors + co2factors:
        if benefit in benefits:
            benefits[benefit] *= LBS_PER_KG

    if 'hydro_interception' in benefits:
        benefits['hydro_interception'] *= GAL_PER_CUBIC_M

    factor_conversions = instance.factor_conversions

    for benefit in benefits:
        value = benefits.get(benefit, 0)

        if factor_conversions and value and benefit in factor_conversions:
            currency = factor_conversions[benefit] * value
        else:
            currency = 0.0

        benefits[benefit] = (value, currency)

    if 'natural_gas' in benefits:
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
                       'unit': unit,
                       'unit-name': 'eco',
                       'label': benefit_labels[group]}

    return {'plot': rslt}


#TODO: Does this helper exist?
def _sum_dict(d1, d2):
    if d1 is None:
        return d2
    if d2 is None:
        return d1

    dsum = {}
    for k in d1.keys() + d2.keys():
        if k in d1 and k not in d2:
            dsum[k] = d1[k]
        elif k in d2 and k not in d1:
            dsum[k] = d2[k]
        else:
            dsum[k] = d1[k] + d2[k]

    return dsum


def _benefits_for_class(cls, filter):
    benefits_fn = cls.benefits.benefits_for_filter
    compute_benefits = lambda: benefits_fn(filter.instance, filter)

    return get_cached_benefits(cls.__name__, filter, compute_benefits)


def _combine_benefit_basis(basis, new_basis_groups):
    for basis_group in new_basis_groups:
        current_group_basis = basis.get(basis_group)
        new_feature_class_basis = new_basis_groups[basis_group]
        basis[basis_group] = _sum_dict(
            current_group_basis, new_feature_class_basis)


def _combine_grouped_benefits(benefits, new_benefit_groups):
    for group, ft_benefits in new_benefit_groups.iteritems():
        for ft_benefit_key, ft_benefit in ft_benefits.iteritems():
            if group not in benefits:
                benefits[group] = {}

            bgroup = benefits[group]

            # If two items from the same group have the
            # same key merge their currency and values:
            if ft_benefit_key in bgroup:
                existing_benefit = bgroup[ft_benefit_key]

                existing_benefit['value'] += ft_benefit['value']

                # Currency may be none in one or both of these
                # which has special meaning so we need to handle
                # it as such
                existing_currency = existing_benefit.get('currency', None)
                ft_currency = ft_benefit.get('currency', None)

                if existing_currency is None:
                    existing_currency = ft_currency
                elif ft_currency is not None:
                    existing_currency += ft_currency

                existing_benefit['currency'] = existing_currency
            else:
                bgroup[ft_benefit_key] = ft_benefit


def _annotate_basis_with_extra_stats(basis):
    # Basis groups just have # calc and # discarded
    # annotate with some more info
    for abasis in basis.values():
        total = (abasis['n_objects_used'] +
                 abasis['n_objects_discarded'])

        abasis['n_total'] = total

        if total != 0:
            pct = abasis['n_objects_used'] / float(total)
            abasis['n_pct_calculated'] = pct


def get_benefits_for_filter(filter):
    benefits, basis = {}, {}

    for C in filter.instance.map_feature_classes:
        ft_benefit_groups, ft_basis = _benefits_for_class(C, filter)

        _combine_benefit_basis(basis, ft_basis)
        _combine_grouped_benefits(benefits, ft_benefit_groups)

    _annotate_basis_with_extra_stats(basis)

    return benefits, basis


def within_itree_regions(request):
    from treemap.models import ITreeRegion
    x = request.GET.get('x', None)
    y = request.GET.get('y', None)
    return (bool(x) and bool(y) and
            ITreeRegion.objects
            .filter(geometry__contains=Point(float(x),
                                             float(y))).exists())

benefit_labels = {
    # Translators: 'Energy conserved' is the name of an eco benefit
    BenefitCategory.ENERGY:     _('Energy conserved'),
    # Translators: 'Stormwater filtered' is the name of an eco benefit
    BenefitCategory.STORMWATER: _('Stormwater filtered'),
    # Translators: 'Carbon dioxide removed' is the name of an eco benefit
    BenefitCategory.CO2:        _('Carbon dioxide removed'),
    # Translators: 'Carbon dioxide stored' is the name of an eco benefit
    BenefitCategory.CO2STORAGE: _('Carbon dioxide stored to date'),
    # Translators: 'Air quality improved' is the name of an eco benefit
    BenefitCategory.AIRQUALITY: _('Air quality improved')
}


_itree_codes_by_region = None
_all_itree_codes = None


def all_itree_codes():
    _ensure_itree_codes_fetched()
    return _all_itree_codes


def has_itree_code(region_code, itree_code):
    _ensure_itree_codes_fetched()
    has = itree_code in _itree_codes_by_region.get(region_code, [])
    return has


def _ensure_itree_codes_fetched():
    global _itree_codes_by_region, _all_itree_codes
    if _itree_codes_by_region is None:
        result, err = ecobackend.json_benefits_call('itree_codes.json', {})
        if err:
            raise Exception('Failed to retrieve i-Tree codes from ecoservice')

        _itree_codes_by_region = result['Codes']

        _all_itree_codes = set(
            itertools.chain(*_itree_codes_by_region.values()))


within_itree_regions_view = json_api_call(within_itree_regions)

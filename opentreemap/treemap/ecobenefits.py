# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.utils.translation import ugettext_lazy as trans
from django.db.models.query import QuerySet
from django.shortcuts import get_object_or_404
from django.contrib.gis.geos.point import Point

from eco.core import Benefits, sum_factor_and_conversion

from treemap.models import Tree
from treemap.decorators import instance_request, json_api_call, strip_request
from treemap.species import CODES
from treemap.models import ITreeRegion


def _all_region_codes():
    return CODES.keys()


def all_species_codes():
    return species_codes_for_regions(_all_region_codes())


def species_codes_for_regions(region_codes):
    if region_codes is None:
        return None
    species_codes = []
    for region_code in region_codes:
        species_codes.extend(CODES[region_code])
    # Converting to a set removes duplicates
    return list(set(species_codes))


_benefit_labels = {
    # Translators: 'Energy' is the name of an eco benefit
    'energy':     trans('Energy'),
    # Translators: 'Stormwater' is the name of an eco benefit
    'stormwater': trans('Stormwater'),
    # Translators: 'Carbon Dioxide' is the name of an eco benefit
    'co2':        trans('Carbon Dioxide'),
    # Translators: 'Air Quality' is the name of an eco benefit
    'airquality': trans('Air Quality')
}


def get_benefit_label(benefit_name):
    return _benefit_labels[benefit_name]


def get_trees_for_eco(trees):
    """
    Converts a QuerySet of trees, a single tree, or any iterable of trees into
    input appropriate for _benefits_for_trees
    """
    if isinstance(trees, QuerySet):
        return trees.exclude(species__otm_code__isnull=True)\
                    .exclude(diameter__isnull=True)\
                    .values('diameter', 'species__otm_code', 'plot__geom')

    if not hasattr(trees, '__iter__'):
        trees = (trees,)

    return [{'diameter': tree.diameter,
             'species__otm_code': tree.species.otm_code,
             'plot__geom': tree.plot.geom}
            for tree in trees
            if tree.diameter is not None and tree.species is not None]


def get_codes_for_species(species, region):
    "Get the iTree codes for a specific in a specific region"
    benefits = Benefits()
    codes = benefits.lookup_species_code(
        region=region, species=species.species, genus=species.genus)

    return codes


def itree_code_for_species_in_region(otm_code, region):
    if region in CODES:
        if otm_code in CODES[region]:
            return CODES[region][otm_code]
    return None


def _benefits_for_trees(trees, instance):
    # A species may be assigned to a tree for which there is
    # no itree code defined for the region in which the tree is
    # planted. This counter keeps track of the number of
    # trees for which the itree code lookup was successful
    num_trees_used_in_calculation = 0

    factor_conversions = instance.factor_conversions

    regions = ITreeRegion.objects.filter(geometry__intersects=instance.bounds)\
                                 .distance(instance.center)\
                                 .order_by('distance')

    # Using prepared geometries provides a 40% perfomance boost
    for region in regions:
        region.prepared_geometry = region.geometry.prepared

    trees_by_region = {}
    for tree in trees:
        region_code = instance.itree_region_default
        for region in regions:
            if region.prepared_geometry.contains(tree['plot__geom']):
                region_code = region.code
                break

        if region_code is not None:
            itree_code = itree_code_for_species_in_region(
                tree['species__otm_code'], region_code)

            if itree_code is not None:
                if region_code not in trees_by_region:
                    trees_by_region[region_code] = []

                trees_by_region[region_code].append((itree_code,
                                                     tree['diameter']))
                num_trees_used_in_calculation += 1

    kwh, gal, co2, aq = [], [], [], []

    for (region_code, trees) in trees_by_region.iteritems():
        benefits = Benefits(factor_conversions)

        kwh.append(benefits.get_energy_conserved(region_code, trees))
        gal.append(benefits.get_stormwater_management(region_code, trees))
        co2.append(benefits.get_co2_stats(region_code, trees)['reduced'])
        aq.append(benefits.get_air_quality_stats(region_code,
                                                 trees)['improvement'])

    # sum_factor_and_conversion returns an empty list when given one
    # so we need to provide a saner default
    def sum_factors(factors_list):
        return sum_factor_and_conversion(*factors_list) or (0.0, None)

    kwh = sum_factors(kwh)
    gal = sum_factors(gal)
    co2 = sum_factors(co2)
    aq = sum_factors(aq)

    def fmt(factor_and_currency, lbl):
        return {'value': factor_and_currency[0],
                'currency': factor_and_currency[1],
                'unit': lbl}

    rslt = {'energy': fmt(kwh, 'kwh'),
            'stormwater': fmt(gal, 'gal'),
            'co2': fmt(co2, 'lbs/year'),
            'airquality': fmt(aq, 'lbs/year')}

    return (rslt, num_trees_used_in_calculation)


def tree_benefits(instance, tree_id):
    """Given a tree id, determine eco benefits via eco.py"""
    InstanceTree = instance.scope_model(Tree)
    tree = get_object_or_404(InstanceTree, pk=tree_id)

    if not tree.diameter:
        rslt = {'benefits': {}, 'error': 'MISSING_DBH'}
    elif not tree.species:
        rslt = {'benefits': {}, 'error': 'MISSING_SPECIES'}
    else:
        rslt = {'benefits':
                _benefits_for_trees(get_trees_for_eco(tree), instance)}

    return rslt


def within_itree_regions(request):
    x = request.GET.get('x', None)
    y = request.GET.get('y', None)
    return (bool(x) and bool(y) and
            ITreeRegion.objects
            .filter(geometry__contains=Point(float(x),
                                             float(y))).exists())

within_itree_regions_view = json_api_call(within_itree_regions)

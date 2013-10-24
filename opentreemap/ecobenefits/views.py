from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.shortcuts import get_object_or_404
from django.contrib.gis.geos.point import Point

from eco import benefits

from treemap.models import Tree
from treemap.util import instance_request, json_api_call, strip_request

from ecobenefits.models import ITreeRegion

from ecobenefits import CODES


def get_codes_for_species(species, region):
    "Get the iTree codes for a specific in a specific region"
    codes = benefits.lookup_species_code(
        region=region, species=species.species, genus=species.genus)

    return codes


def _itree_code_for_species_in_region(otm_code, region):
    if region in CODES:
        if otm_code in CODES[region]:
            return CODES[region][otm_code]
    return None


def _benefits_for_trees(trees, region_default=None):
    # A species may be assigned to a tree for which there is
    # no itree code defined for the region in which the tree is
    # planted. This counter keeps track of the number of
    # trees for which the itree code lookup was successful
    num_trees_used_in_calculation = 0

    regions = {}
    for tree in trees:
        region_code = tree['itree_region_code']
        if region_code is None:
            region_code = region_default

        if region_code is not None:
            if region_code not in regions:
                regions[region_code] = []

            itree_code = _itree_code_for_species_in_region(
                tree['species__otm_code'], region_code)

            if itree_code is not None:
                regions[region_code].append((itree_code, tree['diameter']))
                num_trees_used_in_calculation += 1

    kwh, gal, co2, airq = 0.0, 0.0, 0.0, 0.0

    for (region_code, trees) in regions.iteritems():
        kwh += benefits.get_energy_conserved(
            region_code, trees)
        gal += benefits.get_stormwater_management(
            region_code, trees)
        co2 += benefits.get_co2_stats(
            region_code, trees)['reduced']
        airq += benefits.get_air_quality_stats(
            region_code, trees)['improvement']

    def fmt(val, lbl):
        return {'value': val, 'unit': lbl}

    rslt = {'energy': fmt(kwh, 'kwh'),
            'stormwater': fmt(gal, 'gal'),
            'co2': fmt(co2, 'lbs/year'),
            'airquality': fmt(airq, 'lbs/year')}

    return (rslt, num_trees_used_in_calculation)


def tree_benefits(instance, tree_id):
    "Given a tree id, determine eco benefits via eco.py"
    InstanceTree = instance.scope_model(Tree)
    tree = get_object_or_404(InstanceTree, pk=tree_id)
    dbh = tree.diameter
    otm_code = tree.species.otm_code

    region_list = list(ITreeRegion.objects.filter(
        geometry__contains=tree.plot.geom))
    if len(region_list) > 0:
        region_code = region_list[0].code
    else:
        region_code = instance.itree_region_default

    rslt = {}
    if not dbh:
        rslt = {'benefits': {}, 'error': 'MISSING_DBH'}
    elif not otm_code:
        rslt = {'benefits': {}, 'error': 'MISSING_SPECIES'}
    else:
        rslt = {'benefits':
                _benefits_for_trees(
                    [{'species__otm_code': otm_code,
                      'diameter': dbh,
                      'itree_region_code': region_code}])}

    return rslt


def within_itree_regions(request):
    x = request.GET.get('x', None)
    y = request.GET.get('y', None)
    return (bool(x) and bool(y) and
            ITreeRegion.objects
            .filter(geometry__contains=Point(float(x),
                                             float(y))).exists())

within_itree_regions_view = json_api_call(within_itree_regions)

tree_benefits_view = json_api_call(
    instance_request(strip_request(tree_benefits)))

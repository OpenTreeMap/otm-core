from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.shortcuts import get_object_or_404

from eco import benefits

from treemap.models import Tree
from treemap.util import instance_request, json_api_call, strip_request

from ecobenefits.models import ITreeRegion


def get_codes_for_species(species, region):
    "Get the iTree codes for a specific in a specific region"
    codes = benefits.lookup_species_code(
        region=region, species=species.species, genus=species.genus)

    return codes


def _benefits_for_trees(trees, region_default=None):
    # TODO: actually use region_default
    regions = {}
    for tree in trees:
        region = tree['itree_region_code']
        if region not in regions:
            regions[region] = []

        regions[region].append((tree['species__itree_code'],
                                tree['diameter']))

    kwh, gal, co2, airq = 0.0, 0.0, 0.0, 0.0

    for (region, trees) in regions.iteritems():
        kwh += benefits.get_energy_conserved(region, trees)
        gal += benefits.get_stormwater_management(region, trees)
        co2 += benefits.get_co2_stats(region, trees)['reduced']
        airq += benefits.get_air_quality_stats(region, trees)['improvement']

    def fmt(val, lbl):
        return {'value': val, 'unit': lbl}

    rslt = {'energy': fmt(kwh, 'kwh'),
            'stormwater': fmt(gal, 'gal'),
            'co2': fmt(co2, 'lbs/year'),
            'airquality': fmt(airq, 'lbs/year')}

    return (rslt, len(trees))


def tree_benefits(instance, tree_id):
    "Given a tree id, determine eco benefits via eco.py"
    InstanceTree = instance.scope_model(Tree)
    tree = get_object_or_404(InstanceTree, pk=tree_id)

    dbh = tree.diameter
    species = tree.species.itree_code

    region = ITreeRegion.objects.filter(
        geometry__contains=tree.plot.geom)[0].code

    rslt = {}
    if not dbh:
        rslt = {'benefits': {}, 'error': 'MISSING_DBH'}
    elif not species:
        rslt = {'benefits': {}, 'error': 'MISSING_SPECIES'}
    else:
        rslt = {'benefits':
                _benefits_for_trees(
                    [{'species__itree_code': species,
                      'diameter': dbh,
                      'itree_region_code': region}])}

    return rslt

tree_benefits_view = json_api_call(
    instance_request(strip_request(tree_benefits)))

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.shortcuts import get_object_or_404
from django.http import HttpResponse

from treemap.models import Tree
from treemap.views import instance_request

from eco import benefits

import json


def get_codes_for_species(species, region):
    "Get the iTree codes for a specific in a specific region"
    return benefits.lookup_species_code(
        region=region, species=species.species, genus=species.genus)


def _benefits_for_tree_dbh_and_species(dbh, species, region):
    "Given a dbh, species and region return benefits from eco.py"
    dbh = float(dbh)

    codes = get_codes_for_species(species, region)

    kwh = benefits.get_energy_conserved(region, codes, dbh)
    gal = benefits.get_stormwater_management(region, codes, dbh)
    co2 = benefits.get_co2_stats(region, codes, dbh)
    airq = benefits.get_air_quality_stats(region, codes, dbh)

    def fmt(val, lbl):
        return {'value': val, 'unit': lbl}

    rslt = {'energy': fmt(kwh, 'kwh'),
            'stormwater': fmt(gal, 'gal'),
            'co2': fmt(co2['reduced'], 'lbs/year'),
            'airquality': fmt(airq['improvement'], 'lbs/year')}

    return rslt


@instance_request
def tree_benefits(request, tree_id, region='SoCalCSMA'):
    "Given a tree id, determine eco benefits via eco.py"
    InstanceTree = request.instance.scope_model(Tree)
    tree = get_object_or_404(InstanceTree, pk=tree_id)

    dbh = tree.diameter
    species = tree.species

    rslt = {}
    if not dbh:
        rslt = {'benefits': {}, 'error': 'MISSING_DBH'}
    elif not species:
        rslt = {'benefits': {}, 'error': 'MISSING_SPECIES'}
    else:
        rslt = {'benefits':
                _benefits_for_tree_dbh_and_species(dbh, species, region)}

    return HttpResponse(json.dumps(rslt), content_type='application/json')

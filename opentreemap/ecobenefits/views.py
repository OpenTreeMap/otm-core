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
    return benefits.lookup_species_code(
        region=region, species=species.species, genus=species.genus)

#
# DUMMY METHOD - to be replaced when we have filtering
# working
#
def _execute_filter(instance, filter_str):
    return Tree.objects.filter(instance=instance)

def _benefits_for_tree_dbh_and_species(dbh, species, region):
    dbh = float(dbh)

    codes = get_codes_for_species(species, region)

    kwh = benefits.get_energy_conserved(region, codes, dbh)
    gal = benefits.get_stormwater_management(region, codes, dbh)
    co2 = benefits.get_co2_stats(region, codes, dbh)
    aq = benefits.get_air_quality_stats(region, codes, dbh)

    def fmt(val, lbl):
        return {'value': val, 'unit': lbl }

    rslt = {'energy': fmt(kwh,'kwh'),
            'stormwater': fmt(gal,'gal'),
            'co2': fmt(co2['reduced'],'lbs/year'),
            'airquality': fmt(aq['improvement'],'lbs/year')}

    return rslt

@instance_request
def group_tree_benefits(request, region='SoCalCSMA'):
    filter_str = request.REQUEST['filter']
    trees = _execute_filter(request.instance, filter_str)

    num_calculated_trees = 0

    benefits = {'energy': 0.0, 'stormwater': 0.0,
                'co2': 0.0, 'airquality': 0.0}

    for tree in trees:
        if tree.diameter and tree.species:
            tree_benefits = _benefits_for_tree_dbh_and_species(
                tree.diameter, tree.species, region)

            for key in benefits:
                benefits[key] = tree_benefits[key]['value']

            num_calculated_trees += 1

    total_trees = len(trees)
    if num_calculated_trees > 0 and total_trees > 0:

        # Extrapolate an average over the rest of the urban forest
        trees_without_benefit_data = total_trees - num_calculated_trees
        for benefit in benefits:
            avg_benefit = benefits[benefit] / num_calculated_trees
            extrp_benefit = avg_benefit * trees_without_benefit_data

            benefits[benefit] += extrp_benefit

        rslt = {'benefits': benefits,
                'basis': {'n_calc': num_calculated_trees,
                          'n_total': total_trees,
                          'percent': float(num_calculated_trees)/total_trees }}
    else:
        rslt = {'benefits': benefits,
                'basis': {'n_calc': num_calculated_trees,
                          'n_total': total_trees,
                          'percent': 0}}

    return HttpResponse(json.dumps(rslt), content_type='application/json')


@instance_request
def tree_benefits(request, tree_id, region='SoCalCSMA'):
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

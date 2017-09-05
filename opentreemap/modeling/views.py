# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.contrib.gis.geos import Point
from django.utils.translation import ugettext_lazy as _

import json
import logging

import itertools

from treemap import ecobackend
from treemap.ecobenefits import compute_currency_and_transform_units
from treemap.lib import format_benefits
from treemap.models import Species, Boundary
from treemap.units import (get_units, storage_to_instance_units_factor)

from modeling.run_model.GrowthAndMortalityModel import GrowthAndMortalityModel
from modeling.models import Plan

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# -----------------------------------------------------------------------------
# Page context


def get_modeling_context(request, instance):
    model_params = GrowthAndMortalityModel.get_default_params(instance)
    species_for_planting = \
        GrowthAndMortalityModel.get_species_for_planting(instance)

    return {
        'instance_bounds': list(instance.bounds.geom.extent),
        'species_for_planting':  json.dumps(species_for_planting),
        'diameter_units': get_units(instance, 'tree', 'diameter'),
        'has_boundaries': instance.scope_model(Boundary).exists(),
        'default_model_params': json.dumps(model_params),
        'plans': get_plans_context(request, instance),
        'itree_region_count': len(instance.itree_regions()),
        'support_email': settings.SUPPORT_EMAIL_ADDRESS
    }


# -----------------------------------------------------------------------------
# Plan CRUD


def get_plans_context(request, instance):
    filter = request.GET.get('filter', 'user')
    sort = request.GET.get('sort', '-modified_time')
    page_number = int(request.GET.get('page', '1'))
    page_size = int(request.GET.get('size', '10'))

    plans = Plan.objects.filter(instance=instance)

    if filter == 'user':
        plans = plans.filter(owner=request.user)
    elif filter == 'public':
        plans = plans.filter(is_published=True).exclude(owner=request.user)

    plans = plans.order_by(sort)

    paginator = Paginator(plans, page_size)
    plans = paginator.page(min(page_number, paginator.num_pages))

    def urlize(*keys):
        return '&'.join(['%s=%s' % (key, params[key]) for key in keys])

    plans_url = reverse('plans', args=(instance.url_name,))
    params = {'filter': filter, 'sort': sort, 'page': plans.number}
    url = plans_url + '?'
    url_for_paging = url + urlize('filter', 'sort')
    url_for_sort = url + urlize('filter')
    url_for_filter = url + urlize('sort')

    query_string_for_delete = '?' + urlize('page', 'filter', 'sort')

    filters = [
        {'name': 'user', 'label': _('My plans')},
        {'name': 'public', 'label': _('All public plans')},
    ]

    columns = [
        {'field': 'name', 'label': _('Title')},
        {'field': 'owner__username', 'label': _('Created by')},
        {'field': 'modified_time', 'label': _('Last updated')},
    ]

    return {
        'plans': plans,
        'filters': filters,
        'columns': columns,
        'current_filter': filter,
        'current_sort': sort,
        'url_for_paging': url_for_paging,
        'url_for_sort': url_for_sort,
        'url_for_filter': url_for_filter,
        'query_string_for_delete': query_string_for_delete,
    }


def get_plan(request, instance, plan_id):
    plan = get_object_or_404(Plan, instance=instance, pk=plan_id)
    if plan.is_published or request.user.id == plan.owner_id:
        return plan.to_json()
    else:
        raise PermissionDenied


def add_plan(request, instance):
    plan = Plan()
    plan.instance = instance
    plan.owner = request.user
    plan_dict = json.loads(request.body)
    return _update_plan(plan, plan_dict)


@transaction.atomic
def update_plan(request, instance, plan_id):
    try:
        plan = Plan.objects \
            .select_for_update() \
            .get(instance=instance, pk=plan_id, owner_id=request.user.id)
    except Plan.DoesNotExist:
        raise Http404('No Plan matches the given query.')

    plan_dict = json.loads(request.body)
    if 'force' in request.GET:
        plan_dict['revision'] = plan.revision + 1

    elif 'revision' in plan_dict:
        if plan_dict['revision'] != plan.revision:
            return HttpResponse('Stale revision', status=409)
        plan_dict['revision'] += 1

    return _update_plan(plan, plan_dict)


def _update_plan(plan, plan_dict):
    plan.update(plan_dict)
    plan.save()
    return {
        'id': plan.id,
        'revision': plan.revision
    }


def delete_plan(request, instance, plan_id):
    plan = get_object_or_404(Plan, instance=instance, pk=plan_id,
                             owner_id=request.user.id)
    plan.delete()
    return get_plans_context(request, instance)

# -----------------------------------------------------------------------------
# Scenarios


def run_model(request, instance):
    params = json.loads(request.body)

    model_params = params['model_params']
    scenario = params['scenario_params']

    growth_model = GrowthAndMortalityModel(model_params, instance)

    # TODO: look up region code for each tree and group
    # TODO: this will crash if run for an instance outside
    # of the united states
    region_code = instance.itree_regions()[0].code

    scenario = _prepare_scenario(scenario, instance, region_code)

    return _run_model(instance, growth_model, scenario, region_code)


def _prepare_scenario(scenario, instance, region_code):
    cm_to_instance = _cm_to_instance_diameter_units(instance)
    to_cm = 1.0 / cm_to_instance

    def get_species(otm_code, region_code):
        species = Species.get_by_code(instance, otm_code, region_code)
        if species is None:
            raise Http404(
                "Could not find species with OTM code %s in instance %s"
                % (otm_code, instance.url_name))
        # The species may have been retrieved via an ITreeCodeOverride. In that
        # case, the species will not have an otm_code value and we need to set
        # it so it is available for the downstream code.
        if species.otm_code != otm_code:
            species.otm_code = otm_code
        print(species.common_name)
        return species

    def prepare_tree(tree):
        species = get_species(tree['species'], region_code)
        diameter = tree['diameter'] * to_cm
        trees = [
            {
                'species': species,
                'diameter': diameter,
            }
            for i in range(0, tree['count'])
        ]
        return trees

    def prepare_group(distribution):
        return {
            'species': get_species(distribution['species'], region_code),
            'diameter': distribution['diameter'] * to_cm,
            'count': distribution['count'],
        }

    replanting = scenario['replanting']
    replant_years = replanting['nYears'] if replanting['enable'] else 0

    scenario = {
        'trees': _flatten([prepare_tree(tree) for tree in scenario['trees']]),
        'groups': [prepare_group(dist) for dist in scenario['distributions']],
        'years': 30,  # TODO: pass years from UI
        'replant_years': replant_years
    }
    return scenario


def _flatten(list_of_lists):
    # http://stackoverflow.com/a/953097/362702
    return list(itertools.chain.from_iterable(list_of_lists))


def get_boundaries_at_point(request, instance):
    lat = float(request.GET.get('lat'))
    lng = float(request.GET.get('lng'))
    point = Point(lng, lat, srid=4326)

    boundaries = instance.scope_model(Boundary) \
        .filter(geom__contains=point) \
        .order_by('-sort_order', 'category', 'name')

    for boundary in boundaries:
        boundary.geom.transform(4326)

    boundaries = [{'name': boundary.name,
                   'geom': boundary.geom.geojson}
                  for boundary in boundaries]

    return boundaries


def _run_model(instance, growth_model, scenario, region_code):
    n_years = scenario['years']

    yearly_counts, planted_trees = growth_model.run(scenario)

    eco_trees = _model_trees_to_eco_trees(planted_trees, region_code)
    eco_input = {
        'region': region_code,
        'instance_id': str(instance.id),
        'years': n_years,
        'scenario_trees': eco_trees
    }

    eco, err = ecobackend.json_benefits_call('eco_scenario.json',
                                             eco_input,
                                             post=True,
                                             convert_params=False)
    if err:
        raise Exception(err)

    total_eco = compute_currency_and_transform_units(instance, eco['Total'])
    total_eco = format_benefits(instance, total_eco, None, digits=0)
    currency_symbol = total_eco['currency_symbol']
    total_eco = _list_for_display(total_eco['benefits'])

    yearly_eco = [compute_currency_and_transform_units(instance, benefits)
                  for benefits in eco['Years']]
    yearly_eco = [_list_for_display(benefits) for benefits in yearly_eco]

    yearly_eco_condensed = yearly_eco[0]

    for i in range(0, len(yearly_eco_condensed)):
        yearly_eco_condensed[i] = {
            'label': yearly_eco_condensed[i]['label'],
            'unit': yearly_eco_condensed[i]['unit'],
            'values': [benefits[i]['value'] for benefits in yearly_eco],
            'currencies': [benefits[i]['currency'] for benefits in yearly_eco]
        }

    year_headers = [_('Year %(n)s' % {'n': i}) for i in range(1, n_years + 1)]
    growth_csv_data = _growth_csv_data(instance, year_headers, planted_trees)

    return {
        'years': n_years,
        'yearly_counts': yearly_counts,
        'total_eco': total_eco,
        'yearly_eco': yearly_eco_condensed,
        'currency_symbol': currency_symbol,
        'currency_axis_label': "%s %s" % (currency_symbol, _('saved')),
        'eco_csv_header': _eco_csv_header(year_headers),
        'growth_csv_data': growth_csv_data,
        }


def _list_for_display(benefits):
    benefits = benefits['plot']
    the_list = [
        benefits['energy'],
        benefits['stormwater'],
        benefits['airquality'],
        benefits['co2'],
        # CO2 storage is "over the life of the trees". We'd need to
        #   - use the final value for each tree (not a sum over all years)
        #   - subtract the values for dead trees?
        # Leaving it out for now.
        #
        # benefits['co2storage'],
    ]
    return the_list


def _model_trees_to_eco_trees(planted_trees, region_code):
    eco_trees = [
        {
            'otmcode': tree.species.otm_code,
            'species_id': tree.species.id,
            'region': region_code,
            'diameters': tree.diameters_for_eco()
        }
        for tree in planted_trees]
    return eco_trees


def _eco_csv_header(year_headers):
    header = ['', _('Total')]
    header.extend(year_headers)
    return header


def _growth_csv_data(instance, year_headers, planted_trees):
    diameter_unit = get_units(instance, 'tree', 'diameter')
    header = [
        _('Tree ID'),
        _('Common Name'),
        _('Scientific Name'),
        _('Year 0 Diameter (%(unit)s)' % {'unit': diameter_unit}),
        ]
    header.extend(year_headers)
    rows = [header]

    cm_to_instance = _cm_to_instance_diameter_units(instance)

    for tree in planted_trees:
        row = [
            tree.id,
            tree.species.common_name,
            tree.species.scientific_name,
        ]
        diameters = [d * cm_to_instance for d in tree.diameters_for_export()]
        row.extend(diameters)
        rows.append(row)

    return rows


def _cm_to_instance_diameter_units(instance):
    # Get conversion factor from cm to instance's diameter units.
    # We know that OTM stores tree diameters in inches, so go from
    # cm to inches to instance units.
    in_to_instance = storage_to_instance_units_factor(instance,
                                                      'tree', 'diameter')
    cm_to_in = 1 / 2.54
    cm_to_instance = cm_to_in * in_to_instance
    return cm_to_instance

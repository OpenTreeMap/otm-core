from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from functools import wraps
from itertools import chain

import json

from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.http import (HttpResponse, HttpResponseBadRequest,
                         HttpResponseServerError)

from django.views.decorators.http import etag

from django.conf import settings
from treemap.search import create_filter

from treemap.models import Instance, Plot, Audit, Tree, User, Boundary
from ecobenefits.models import _benefits_for_tree_dbh_and_species


class InvalidInstanceException(Exception):
    pass


class HttpBadRequestException(Exception):
    pass


def instance_request(view_fn):
    @wraps(view_fn)
    def wrapper(request, instance_id, *args, **kwargs):
        request.instance = get_object_or_404(Instance, pk=instance_id)
        return view_fn(request, *args, **kwargs)

    return wrapper


def json_api_call(req_function):
    """ Wrap a view-like function that returns an object that
        is convertable from json
    """
    @wraps(req_function)
    def newreq(request, *args, **kwargs):
        try:
            outp = req_function(request, *args, **kwargs)
            if issubclass(outp.__class__, HttpResponse):
                response = outp
            else:
                response = HttpResponse()
                response.write('%s' % json.dumps(outp))
                response['Content-length'] = str(len(response.content))

            response['Content-Type'] = "application/json"

        except HttpBadRequestException, bad_request:
            response = HttpResponseBadRequest(bad_request.message)

        return response
    return newreq


@instance_request
def index(request):
    return render_to_response('treemap/index.html', RequestContext(request))


@instance_request
def trees(request):
    return render_to_response('treemap/map.html', RequestContext(request))


def _plot_hash(request, plot_id):
    return request.instance.scope_model(Plot).get(pk=plot_id).hash


@instance_request
@etag(_plot_hash)
def plot_detail(request, plot_id):
    InstancePlot = request.instance.scope_model(Plot)
    plot = get_object_or_404(InstancePlot, pk=plot_id)

    return render_to_response('treemap/plot_detail.html', {
        'plot': plot
    }, RequestContext(request))


@instance_request
def settings_js(request):
    return render_to_response('treemap/settings.js',
                              {'BING_API_KEY': settings.BING_API_KEY},
                              RequestContext(request),
                              mimetype='application/x-javascript')


@instance_request
@json_api_call
def audits(request):
    """
    Request a variety of different audit types.
    Params:
       - models
         Comma separated list of models (only Tree and Plot are supported)
       - model_id
         The ID of a specfici model. If specified, models must also
         be defined and have only one model

       - user
         Filter by a specific user

       - include_pending (default: true)
         Set to false to ignore edits that are currently pending

       - page_size
         Size of each page to return (up to PAGE_MAX)
       - page
         The page to return
    """

    PAGE_MAX = 100

    r = request.REQUEST
    instance = request.instance

    page_size = min(int(r.get('page_size', PAGE_MAX)), PAGE_MAX)
    page = int(r.get('page', 0))

    start_pos = page * page_size
    end_pos = start_pos + page_size

    models = []

    allowed_models = {
        'tree': 'Tree',
        'plot': 'Plot'
    }

    for model in r.get('models', "tree,plot").split(','):
        if model.lower() in allowed_models:
            models.append(allowed_models[model.lower()])
        else:
            raise Exception("Invalid model: %s" % model)

    model_id = r.get('model_id', None)

    if model_id is not None and len(models) != 1:
        raise Exception("You must specific one and only model "
                        "when looking up by id")

    user_id = r.get('user', None)
    user = None

    if user_id is not None:
        user = User.objects.get(pk=user_id)

    audits = Audit.objects.filter(instance=instance)\
                          .filter(model__in=models)\
                          .order_by('-created')

    if user_id:
        audits = audits.filter(user=user)

    if model_id:
        audits = audits.filter(model_id=model_id)

    if r.get('include_pending', "true") == "false":
        audits = audits.exclude(requires_auth=True, ref_id__isnull=True)

    return [a.dict() for a in audits[start_pos:end_pos]]


@json_api_call
def boundary_to_geojson(request, boundary_id):
    boundary = Boundary.objects.get(pk=boundary_id)
    return HttpResponse(boundary.geom.geojson)


@json_api_call
@instance_request
def boundary_autocomplete(request):
    query = request.GET.get('q', '')
    max_items = request.GET.get('max_items', 10)

    boundaries = request.instance.boundaries\
                                 .filter(name__startswith=query)\
                                 .order_by('name')[:max_items]

    return [{'name': boundary.name, 'category': boundary.category}
            for boundary in boundaries]


def _execute_filter(instance, filter_str):
    return create_filter(filter_str).filter(instance=instance)

@instance_request
def search_tree_benefits(request, region='SoCalCSMA'):
    try:
        filter_str = request.REQUEST['filter']
    except KeyError:
        return HttpResponseServerError("Please supply a 'filter' parameter")

    plots  = _execute_filter(request.instance, filter_str)
    trees = chain(*[plot.trees for plot in plots])

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
                          'percent': (float(num_calculated_trees) /
                                      total_trees)}}
    else:
        rslt = {'benefits': benefits,
                'basis': {'n_calc': num_calculated_trees,
                          'n_total': total_trees,
                          'percent': 0}}

    return HttpResponse(json.dumps(rslt), content_type='application/json')

# -*- coding: utf-8 -*-


import json
from functools import wraps

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.contrib.gis.db.models.functions import Distance
from django.http import RawPostDataException

from django_tinsel.exceptions import HttpBadRequestException

from treemap.lib.map_feature import context_dict_for_plot
from treemap.views.map_feature import update_map_feature

from treemap.models import Plot


def transform_plot_update_dict(plot_update_fn):
    """
    Removes some information from the plot response for older APIs

    v5 - universalRev added
    """
    @wraps(plot_update_fn)
    def wrapper(request, *args, **kwargs):
        plot_dict = plot_update_fn(request, *args, **kwargs)

        if request.api_version < 5 and 'universalRevHash' in plot_dict:
            plot_dict['geoRevHash'] = plot_dict['universalRevHash']
            del plot_dict['universalRevHash']
        return plot_dict
    return wrapper


def plots_closest_to_point(request, instance, lat, lng):
    point = Point(float(lng), float(lat), srid=4326)

    try:
        max_plots = int(request.GET.get('max_plots', '1'))

        if max_plots not in range(1, 501):
            raise ValueError()
    except ValueError:
        raise HttpBadRequestException(
            'The max_plots parameter must be a number between 1 and 500')

    try:
        distance = float(request.GET.get(
            'distance', settings.MAP_CLICK_RADIUS))
    except ValueError:
        raise HttpBadRequestException('The distance parameter must be a number')

    #plots = Plot.objects.distance(point)\
    plots = Plot.objects.filter(geom__distance_lte=(point, D(m=distance)))\
                        .annotate(distance=Distance('geom', point))\
                        .order_by('distance')[0:max_plots]

    def ctxt_for_plot(plot):
        return context_dict_for_plot(request, plot)

    return [ctxt_for_plot(plot) for plot in plots]


def get_plot(request, instance, plot_id):
    return context_dict_for_plot(request, Plot.objects.get(pk=plot_id))


def update_or_create_plot(request, instance, plot_id=None):
    # The API communicates via nested dictionaries but
    # our internal functions prefer dotted pairs (which
    # is what inline edit form users)
    # Sometimes reading from body fails, so try reading as a file-like object
    try:
        body_decoded = request.body.decode()
    except RawPostDataException:
        body_decoded = request.read().decode()

    if body_decoded:
        request_dict = json.loads(body_decoded)
    else:
        request_dict = {}

    data = {}

    for model in ["plot", "tree"]:
        if model in request_dict:
            for key, val in request_dict[model].items():
                data["%s.%s" % (model, key)] = val

    # We explicitly disallow setting a plot's tree id.
    # We ignore plot's updated at and by because
    # auditing sets them automatically.
    keys = ["tree.plot",
            "tree.udfs",
            "tree.instance",
            "plot.updated_at",
            "plot.updated_by",
            "plot.instance",
            "plot.udfs"]

    for key in keys:
        if key in data:
            del data[key]

    if "tree.species" in data:
        sp = data["tree.species"]
        if sp and "id" in sp:
            data["tree.species"] = sp['id']
        else:
            data["tree.species"] = None

    if plot_id:
        plot = get_object_or_404(Plot, pk=plot_id, instance=instance)
    else:
        plot = Plot(instance=instance)

    plot, __ = update_map_feature(data, request.user, plot)

    context_dict = context_dict_for_plot(request, plot)

    # Add geo rev hash so clients will know if a tile refresh is required
    context_dict["geoRevHash"] = plot.instance.geo_rev_hash
    context_dict["universalRevHash"] = plot.instance.universal_rev_hash

    return context_dict

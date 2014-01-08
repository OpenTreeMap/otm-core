import json

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D

from treemap.exceptions import HttpBadRequestException

from treemap.views import context_dict_for_plot, update_plot_and_tree
from treemap.models import Plot


def plots_closest_to_point(request, instance, lat, lng):
    point = Point(float(lng), float(lat), srid=4326)

    try:
        max_plots = int(request.GET.get('max_plots', '1'))

        if max_plots not in xrange(1, 501):
            raise ValueError()
    except ValueError:
        raise HttpBadRequestException(
            'The max_plots parameter must be a number between 1 and 500')

    try:
        distance = float(request.GET.get(
            'distance', settings.MAP_CLICK_RADIUS))
    except ValueError:
        raise HttpBadRequestException(
            'The distance parameter must be a number')

    plots = Plot.objects.distance(point)\
                        .filter(instance=instance)\
                        .filter(geom__distance_lte=(point, D(m=distance)))\
                        .order_by('distance')[0:max_plots]

    return [context_dict_for_plot(plot, user=request.user) for plot in plots]


def get_plot(request, instance, plot_id):
    return context_dict_for_plot(Plot.objects.get(pk=plot_id),
                                 user=request.user)


def update_or_create_plot(request, instance, plot_id=None):
    # The API communicates via nested dictionaries but
    # our internal functions prefer dotted pairs (which
    # is what inline edit form users)
    request_dict = json.loads(request.body)

    data = {}

    for model in ["plot", "tree"]:
        if model in request_dict:
            for key, val in request_dict[model].iteritems():
                data["%s.%s" % (model, key)] = val

    # We explicitly disallow setting a plot's tree id
    keys = ["tree.plot",
            "tree.udfs",
            "tree.instance",
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

    plot, _ = update_plot_and_tree(data, request.user, plot)

    return context_dict_for_plot(plot, user=request.user)

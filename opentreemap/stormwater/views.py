# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf import settings
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D

from django_tinsel.exceptions import HttpBadRequestException

from stormwater.models import PolygonalMapFeature


def polygon_for_point(request, instance):
    lng = request.GET['lng']
    lat = request.GET['lat']
    point = Point(float(lng), float(lat), srid=4326)

    try:
        distance = float(request.GET.get(
            'distance', settings.MAP_CLICK_RADIUS))
    except ValueError:
        raise HttpBadRequestException(
            'The distance parameter must be a number')

    features = PolygonalMapFeature.objects.distance(point)\
        .filter(instance=instance)\
        .filter(polygon__distance_lte=(point, D(m=distance)))\
        .order_by('distance')[0:1]

    if len(features) > 0:
        # This is currently only being used to complement UTF grid plot data,
        # so the structure of the response is designed to mirror the utf grid
        return {
            'data': {
                'id': features[0].pk
            }
        }

    return {
        'data': None
    }

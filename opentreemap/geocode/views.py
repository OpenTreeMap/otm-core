# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json

from django.http import HttpResponse
from django.utils.translation import ugettext as _
from django.conf import settings
from django.contrib.gis.geos.point import Point

from django_tinsel.decorators import json_api_call

from omgeo import Geocoder
from omgeo.places import Viewbox, PlaceQuery
from omgeo.services.esri import EsriWGS


geocoder = Geocoder(sources=settings.OMGEO_SETTINGS)
ESRI_WGS = EsriWGS(settings=settings.OMGEO_SETTINGS[0][1]['settings'])


def _omgeo_candidate_to_dict(candidate, srid=3857):
    p = Point(candidate.x, candidate.y, srid=candidate.wkid)
    if candidate.wkid != srid:
        p.transform(srid)
    return {
        'address': candidate.match_addr,
        'region': candidate.match_region,
        'city': candidate.match_city,
        'srid': p.srid,
        'score': candidate.score,
        'x': p.x,
        'y': p.y,
        'type': candidate.locator_type,
    }


def _no_results_response(address, inregion=False):
    response = HttpResponse()
    response.status_code = 404

    if inregion:
        err = _("No results found in the area for %(address)s")
    else:
        err = _("No results found for %(address)s")

    content = {'error': err % {'address': address}}

    response.write(json.dumps(content))
    response['Content-length'] = str(len(response.content))
    response['Content-Type'] = "application/json"
    return response


def _in_bbox(bbox, c):
    x, y = c['x'], c['y']

    valid_x = x >= float(bbox['xmin']) and x <= float(bbox['xmax'])
    valid_y = y >= float(bbox['ymin']) and y <= float(bbox['ymax'])

    return valid_x and valid_y


def _contains_bbox(request):
    return ('xmin' in request.GET and 'ymin' in request.GET and
            'xmax' in request.GET and 'ymax' in request.GET)


def _get_viewbox_from_request(request):
    if _contains_bbox(request):
        xmin, ymin, xmax, ymax = [request.GET[b] for b
                                  in ['xmin', 'ymin', 'xmax', 'ymax']]
        return Viewbox(
            left=float(xmin),
            right=float(xmax),
            bottom=float(ymin),
            top=float(ymax),
            wkid=3857)
    else:
        return None


def geocode(request):
    """
    Search for specified address, returning candidates with lat/long
    """
    key = request.GET.get('key')
    address = request.GET.get('address').encode('utf-8')
    for_storage = 'forStorage' in request.GET

    if key:
        # See settings.OMGEO_SETTINGS for configuration
        pq = PlaceQuery(query=address, key=key, for_storage=for_storage)
        geocode_result = geocoder.geocode(pq)
        candidates = geocode_result.get('candidates', None)
        if candidates:
            # There should only be one candidate since the user already chose a
            # specific suggestion and the front end filters out suggestions
            # that might result in more than one candidate (like "Beaches").
            match = candidates[0]
            return {
                'lat': match.y,
                'lng': match.x
            }

    return _no_results_response(address)


def get_esri_token(request):
    return {'token': ESRI_WGS.get_token()}


geocode_view = json_api_call(geocode)
get_esri_token_view = json_api_call(get_esri_token)

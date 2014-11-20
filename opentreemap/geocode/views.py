# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json

from django.http import HttpResponse
from django.utils.translation import ugettext as trans
from django.conf import settings
from django.contrib.gis.geos.point import Point

from django_tinsel.decorators import json_api_call

from omgeo import Geocoder
from omgeo.places import Viewbox, PlaceQuery


geocoder = Geocoder(sources=settings.OMGEO_SETTINGS)


def _omgeo_candidate_to_dict(candidate, srid=3857):
    p = Point(candidate.x, candidate.y, srid=candidate.wkid)
    if candidate.wkid != srid:
        p.transform(srid)
    return {'address': candidate.match_addr,
            'srid': p.srid,
            'score': candidate.score,
            'x': p.x,
            'y': p.y}


def _no_results_response(address, inregion=False):
    response = HttpResponse()
    response.status_code = 404

    if inregion:
        err = trans("No results found in the area for %(address)s")
    else:
        err = trans("No results found for %(address)s")

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
    return ('xmin' in request.REQUEST and 'ymin' in request.REQUEST and
            'xmax' in request.REQUEST and 'ymax' in request.REQUEST)


def _get_viewbox_from_request(request):
    if _contains_bbox(request):
        xmin, ymin, xmax, ymax = [request.REQUEST[b] for b
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
    Endpoint to geocode a lat/lng pair

    Configuration for sources is pulled from the OMGEO_SETTINGS
    settings key
    """
    viewbox = _get_viewbox_from_request(request)

    address = request.REQUEST['address']

    pq = PlaceQuery(query=address, viewbox=viewbox)

    geocode_result = geocoder.geocode(pq)
    candidates = geocode_result.get('candidates', None)

    if not candidates or len(candidates) == 0:
        return _no_results_response(address)
    else:
        candidates = [_omgeo_candidate_to_dict(c) for c in candidates]

        if _contains_bbox(request):
            bbox = {'xmin': request.REQUEST['xmin'],
                    'ymin': request.REQUEST['ymin'],
                    'xmax': request.REQUEST['xmax'],
                    'ymax': request.REQUEST['ymax']}

            candidates = [c for c in candidates if _in_bbox(bbox, c)]

            if len(candidates) == 0:
                return _no_results_response(address, inregion=True)

        return {'candidates': candidates}


geocode_view = json_api_call(geocode)

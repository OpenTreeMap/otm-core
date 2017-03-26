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


geocoder = Geocoder(sources=settings.OMGEO_SETTINGS, postprocessors=[])
geocoder_for_magic_key = Geocoder(
    sources=settings.OMGEO_SETTINGS_FOR_MAGIC_KEY)
geocoder_for_magic_key = Geocoder([['omgeo.services.Google', {'settings': {'api_key': 'GST7YMc0AM9UOsEqAYatIS9GOghnYnwZIip_GQypG1c915E7QT9tDFcpOh9bZgKZQoc3YSyaagDIZhkZHn5vHSnvC5N7'}}]])

def _omgeo_candidate_to_dict(candidate, srid=3857):

    p = Point(candidate.x, candidate.y, srid=candidate.wkid)
    if candidate.wkid != srid:
        p.transform(srid)
    candidate.locator_type = 'PointAddress'
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
    Search for specified address, returning candidates with lat/long
    """
    key = request.REQUEST.get('key')
    address = request.REQUEST.get('address')
    if key:
        return _geocode_with_magic_key(address, key)
    else:
        return _geocode_without_magic_key(request, address)


def depolonize(address):
    '''remove Polish signs from word'''
    new = ''
    dict_i = {
        'ę' : 'e',
        'Ę' : 'E',
        'ó' : 'o',
        'Ó' : 'O',
        'ą' : 'a',
        'Ą' : 'A',
        'ś' : 's',
        'Ś' : 'S',
        'ł' : 'l',
        'Ł' : 'L',
        'ż' : 'z',
        'Ż' : 'Z',
        'ź' : 'z',
        'Ź' : 'Z',
        'ć' : 'c',
        'Ć' : 'C',
        'ń' : 'n',
        'Ń' : 'N',
    }
    for i in address:
        new = new + dict_i.get(i,i)
    return new


def _geocode_with_magic_key(address, key):
    # See settings.OMGEO_SETTINGS_FOR_MAGIC_KEY for configuration
    address = depolonize(address)
    pq = PlaceQuery(query=address, country='Poland')
    geocode_result = geocoder_for_magic_key.geocode(pq)
    candidates = geocode_result.get('candidates', None)
    if candidates:
        # Address searches return many candidates. But the user already
        # chose a specific suggestion so we want the first candidate.
        # The exception is a "point of interest" search, where the user's
        # chosen suggestion may be a category like "Beaches" and you want to
        # see many candidates.
        # if candidates[0].locator_type != 'POI':
        #     candidates = [candidates[0]]
        # print (candidates)
        candidates = [_omgeo_candidate_to_dict(c) for c in candidates]
        return {'candidates': candidates}
    else:
        return _no_results_response(address)


def _geocode_without_magic_key(request, address):
    # See settings.OMGEO_SETTINGS for configuration
    viewbox = _get_viewbox_from_request(request)
    pq = PlaceQuery(query=address, viewbox=viewbox)
    geocode_result = geocoder.geocode(pq)

    candidates = geocode_result.get('candidates', None)

    if not candidates:
        return _no_results_response(address)
    else:
        candidates = [_omgeo_candidate_to_dict(c) for c in candidates]

        if _contains_bbox(request):
            # The geocoder favored results inside the bounding box but may have
            # returned results outside the bounding box, so filter those away.
            bbox = {'xmin': request.REQUEST['xmin'],
                    'ymin': request.REQUEST['ymin'],
                    'xmax': request.REQUEST['xmax'],
                    'ymax': request.REQUEST['ymax']}

            candidates = [c for c in candidates if _in_bbox(bbox, c)]

            if len(candidates) == 0:
                return _no_results_response(address, inregion=True)

        return {'candidates': candidates}


geocode_view = json_api_call(geocode)
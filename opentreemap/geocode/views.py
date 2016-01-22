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
from omgeo.places import PlaceQuery


geocoder = Geocoder(sources=settings.OMGEO_SETTINGS)


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


def geocode(request):
    """
    Endpoint to geocode a lat/lng pair

    Configuration for sources is pulled from the OMGEO_SETTINGS
    settings key
    """
    key = request.REQUEST.get('key')
    address = request.REQUEST.get('address')

    pq = PlaceQuery(query=address, key=key)

    geocode_result = geocoder.geocode(pq)
    candidates = geocode_result.get('candidates', None)

    if not candidates or len(candidates) == 0:
        return _no_results_response(address)

    candidates = [_omgeo_candidate_to_dict(c) for c in candidates]
    return {'candidates': candidates}


geocode_view = json_api_call(geocode)

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json

from django.http import HttpResponse

from django.conf import settings

from omgeo import Geocoder

from django.contrib.gis.geos.point import Point

from treemap.util import json_api_call


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


def _no_results_response(address):
    response = HttpResponse()
    response.status_code = 404
    content = {'error': "No results found for %s" % address}
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
    address = request.REQUEST['address']
    geocode_result = geocoder.geocode(address)
    candidates = geocode_result.get('candidates', None)
    if candidates and len(candidates) > 0:
        return {'candidates':
                [_omgeo_candidate_to_dict(c) for c in candidates]}
    else:
        return _no_results_response(address)


geocode_view = json_api_call(geocode)

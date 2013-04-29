from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.http import HttpResponse, Http404

from django.views.decorators.http import etag

from django.conf import settings
from django.views.decorators.cache import cache_page

from omgeo import Geocoder

import json

def geocode(request):
    """
    Endpoint to geocode a lat/lng pair

    Configuration for sources is pulled from the OMGEO_SETTINGS
    settings key
    """
    rslt = Geocoder(sources=settings.OMGEO_SETTINGS)\
        .geocode(request.REQUEST['address'])

    candidates = rslt.get('candidates', None)
    if candidates and len(candidates) > 0:
        resp = {'address': candidates[0].match_addr,
                'epsg': candidates[0].wkid,
                'x': candidates[0].x,
                'y': candidates[0].y}

        return HttpResponse(json.dumps(resp))
    else:
        raise Http404('Could not geocode %s' % request.REQUEST['address'])

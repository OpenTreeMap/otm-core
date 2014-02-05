# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import urllib2
import urllib
import json

from django.conf import settings
from django.contrib.gis.db.backends.postgis.adapter import PostGISAdapter
from django.contrib.gis.geos import GEOSGeometry

BAD_CODE_PAIR = 'bad code pair'


def json_benefits_call(endpoint, params, post=False):
    url = "%s/%s" % (settings.ECO_SERVICE_URL, endpoint)

    if post:
        paramdata = {}

        # Group all keys called "param" as a list
        for k, v in params:
            # The postgis adapter stores geometry objects
            # which are not normally serialzable. str(x) will
            # turn it into a ewkb encoded string which doesn't
            # translate well. Instead, we send over ewkt and
            # the associated ST_XXX call
            if isinstance(v, PostGISAdapter):
                bytestring = v.ewkb
                hexstring = ''.join('%02X' % ord(x) for x in bytestring)

                v = "ST_GeomFromEWKT('%s')" % GEOSGeometry(hexstring).ewkt
            else:
                v = str(v)

            if k == "param":
                if k in paramdata:
                    paramdata[k].append(v)
                else:
                    paramdata[k] = [v]
            else:
                paramdata[k] = v

        data = json.dumps(paramdata)
        req = urllib2.Request(url,
                              data,
                              #{'Content-Type': 'application/json'},
                              {'Content-Type': 'text/plain'})
    else:
        paramString = "&".join(["%s=%s" % (urllib.quote_plus(str(name)),
                                           urllib.quote_plus(str(val)))
                                for (name, val) in params])

        # A get request is assumed by urllib2
        req = url + '?' + paramString

    try:
        rslt = json.loads(urllib2.urlopen(req).read())
    except urllib2.HTTPError as e:
        if e.fp.read() == 'invalid otm code for region\n':
            return (None, BAD_CODE_PAIR)
        else:
            raise

    return (rslt, None)

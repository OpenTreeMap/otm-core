# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import urllib2
import urllib
import json
import re

from django.conf import settings
from django.contrib.gis.db.backends.postgis.adapter import PostGISAdapter
from django.contrib.gis.geos import GEOSGeometry

import logging
logger = logging.getLogger(__name__)


# A system for handling unstructured text errors from the ecoservice
#
# Each key in `ECOBENEFIT_ERRORS` has a corresponding template
# block in the plot_detail page that will display a user friendly
# error message, as descriptive as possible.
#
# Each Value in `ECOBENEFIT_ERRORS` is a list of regexps used to
# correctly identify a given error type. They will all be tried in
# succession.
#
# If no pattern is found for any key, a 500 will raise.
#
# TODO: when the ecoservice starts returning structured error output
# replace these patterns with simple destructuring.
#

BAD_CODE_PAIR = 'invalid_eco_pair'
UNKNOWN_ECOBENEFIT_ERROR = 'unknown_ecobenefit_error'
ECOBENEFIT_ERRORS = {
    BAD_CODE_PAIR: [
        (r'iTree code not found for otmcode '
         r'([A-Z]+) in region ([A-Za-z]+)\n')],
    UNKNOWN_ECOBENEFIT_ERROR: [
        'Species data not found for the .* region',
        ('There are overrides defined for instance .* in '
         'the .* region but not for species ID .*'),
        ('There are overrides defined for the instance, '
         'but not for the .* region'),
        'Missing or invalid .* parameter',
    ]
}


def json_benefits_call(endpoint, params, post=False, convert_params=True):
    url = "%s/%s" % (settings.ECO_SERVICE_URL, endpoint)

    if post:
        if convert_params:
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
        else:
            data = json.dumps(params)
        req = urllib2.Request(url,
                              data,
                              {'Content-Type': 'application/json'})
    else:
        paramString = "&".join(["%s=%s" % (urllib.quote_plus(str(name)),
                                           urllib.quote_plus(str(val)))
                                for (name, val) in params])

        # A get request is assumed by urllib2
        req = url + '?' + paramString

    try:
        return (json.loads(urllib2.urlopen(req).read()), None)
    except urllib2.HTTPError as e:
        error_body = e.fp.read()
        logger.warning("ECOBENEFIT FAILURE: " + error_body)
        for code, patterns in ECOBENEFIT_ERRORS.items():
            for pattern in patterns:
                match = re.match(pattern, error_body)
                if match:
                    return (None, code)
        else:
            # the caller decides if it wants to raise the error
            # as an exception, or return it as a status code on
            # a json response. therefore, it's always save to
            # return this string, and never raise.
            return (None, UNKNOWN_ECOBENEFIT_ERROR)

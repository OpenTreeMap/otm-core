# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import urllib2
import urllib
import json
import re
import sys

from django.conf import settings
from django.contrib.gis.db.backends.postgis.adapter import PostGISAdapter
from django.contrib.gis.geos import GEOSGeometry

from opentreemap.util import add_rollbar_handler

import logging

# By default the level for the logger will be NOTSET, which falls back
# to the level set on the root logger, which is WARNING.
#
# https://docs.python.org/dev/library/logging.html#logging.Logger.setLevel
#
# We want to log some non-critical ecobenefit failures as INFO so that
# the WARNING level does not have too many.
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
add_rollbar_handler(logger, level=logging.INFO)

# A system for handling unstructured text errors from the ecoservice
#
# Each key in `ECOBENEFIT_FAILURE_CODES_AND_PATTERNS` has a
# corresponding block in the `plot_eco.html` template that will display a
# user friendly error message, as descriptive as possible.
#
# Each Value in `ECOBENEFIT_FAILURE_CODES_AND_PATTERNS` is a list of
# regexps used to correctly identify a given error type. They will all
# be tried in succession.
#
# If no pattern is found for any key, a 500 will raise.
#
# TODO: when the ecoservice starts returning structured error output
# replace these patterns with simple destructuring.
#

INVALID_ECO_PAIR = 'invalid_eco_pair'
INCOMPLETE_ECO_DATA = 'incomplete_eco_data'
UNKNOWN_ECO_FAILURE = 'unknown_eco_failure'
ECOBENEFIT_FAILURE_CODES_AND_PATTERNS = {
    INVALID_ECO_PAIR: [
        (r'iTree code not found for otmcode '
         r'([A-Z]+) in region ([A-Za-z]+)\n')],
    INCOMPLETE_ECO_DATA: [
        'Species data not found for the .* region',
        ('There are overrides defined for instance .* in '
         'the .* region but not for species ID .*'),
        ('There are overrides defined for the instance, '
         'but not for the .* region')],
    UNKNOWN_ECO_FAILURE: [
        'Missing or invalid .* parameter'
    ]
}
LOG_FUNCTION_FOR_FAILURE_CODE = {
    INVALID_ECO_PAIR: logger.info,
    INCOMPLETE_ECO_DATA: logger.info,
    UNKNOWN_ECO_FAILURE: logger.error,
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
                elif not isinstance(v, unicode):
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

    # the caller decides if it wants to raise the error
    # as an exception, or return it as a status code on
    # a json response. therefore, it's always safe to
    # return this string, and never raise.
    general_unhandled_struct = (None, UNKNOWN_ECO_FAILURE)

    try:
        return (json.loads(urllib2.urlopen(req).read()), None)
    except urllib2.HTTPError as e:
        error_body = e.fp.read()
        for code, patterns in ECOBENEFIT_FAILURE_CODES_AND_PATTERNS.items():
            for pattern in patterns:
                match = re.match(pattern, error_body)
                if match:
                    # When you pass a dictionary to a Python logger's
                    # `extra` kwarg, each key in the dictionary is
                    # added as an attribute on the log message object
                    # itself. Rollbar specifically looks for an
                    # attribute named `extra_data` on the log message.
                    # https://github.com/rollbar/pyrollbar/blob/cbfc2529a2d8847e18f7134aa874eb7c68426e2f/rollbar/logger.py#L97 # NOQA
                    extra = {
                        'extra_data': {
                            'ecobenefit_message': error_body,
                            'ecobenefit_matched_message_pattern': pattern,
                            'ecobenefit_failure_code': code
                        }
                    }
                    # We set the text of the log message to the code
                    # and pattern that were matched rather than the
                    # fully detailed message so that Rollbar can group
                    # and count similar failures.
                    LOG_FUNCTION_FOR_FAILURE_CODE[code](
                        "ECOBENEFIT FAILURE: %s %s " % (code, pattern),
                        extra=extra)
                    return (None, code)
        else:
            # If we did not break out of the loop by returning early
            # that means we received an unknown response from the
            # ecoservice.
            LOG_FUNCTION_FOR_FAILURE_CODE[UNKNOWN_ECO_FAILURE](
                "ECOBENEFIT FAILURE: " + error_body)
            return general_unhandled_struct
    except urllib2.URLError:
        logger.error("Error connecting to ecoservice", exc_info=sys.exc_info())
        return general_unhandled_struct

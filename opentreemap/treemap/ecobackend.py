# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import urllib2
import urllib
import json

from django.conf import settings

BAD_CODE_PAIR = 'bad code pair'

def json_benefits_call(endpoint, params):
    paramString = "&".join(["%s=%s" % (urllib.quote_plus(str(name)),
                                       urllib.quote_plus(str(val)))
                            for (name, val) in params])

    url = "%s/%s?%s" % (settings.ECO_SERVICE_URL,
                        endpoint, paramString)

    try:
        rslt = json.loads(urllib2.urlopen(url).read())
    except urllib2.HTTPError as e:
        if e.fp.read() == 'invalid otm code for region\n':
            return (None, BAD_CODE_PAIR)
        else:
            raise

    return (rslt, None)

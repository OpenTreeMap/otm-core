# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
from django.http import HttpResponseForbidden


class InvalidInstanceException(Exception):
    pass


class FeatureNotEnabledException(Exception):
    pass


class JSONResponseForbidden(HttpResponseForbidden):
    def __init__(self, *args, **kwargs):
        super(JSONResponseForbidden, self).__init__(
            json.dumps({'error': 'Permission Denied'}),
            *args,
            content_type='application/json',
            **kwargs)

# -*- coding: utf-8 -*-




import json
from django.http import HttpResponseForbidden


class InvalidInstanceException(Exception):
    pass


class JSONResponseForbidden(HttpResponseForbidden):
    def __init__(self, *args, **kwargs):
        super(JSONResponseForbidden, self).__init__(
            json.dumps({'error': 'Permission Denied'}),
            *args,
            content_type='application/json',
            **kwargs)

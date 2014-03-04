# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseRedirect, Http404


def route(**kwargs):
    @csrf_exempt
    def routed(request, *args2, **kwargs2):
        method = request.method

        if method not in kwargs:
            raise Http404()
        else:
            req_method = kwargs[method]
            return req_method(request, *args2, **kwargs2)
    return routed


def json_from_request(request):
    body = request.body

    if body:
        return json.loads(body)
    else:
        return None


def merge_view_contexts(viewfns):
    def wrapped(*args, **kwargs):
        context = {}
        for viewfn in viewfns:
            context.update(viewfn(*args, **kwargs))

        return context
    return wrapped

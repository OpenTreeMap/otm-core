import json

from functools import wraps

from django.shortcuts import get_object_or_404
from django.http import HttpResponse, HttpResponseBadRequest

from treemap.models import Instance


class HttpBadRequestException(Exception):
    pass


class InvalidInstanceException(Exception):
    pass


def instance_request(view_fn):
    @wraps(view_fn)
    def wrapper(request, instance_id, *args, **kwargs):
        request.instance = get_object_or_404(Instance, pk=instance_id)
        return view_fn(request, *args, **kwargs)

    return wrapper


def json_api_call(req_function):
    """ Wrap a view-like function that returns an object that
        is convertable from json
    """
    @wraps(req_function)
    def newreq(request, *args, **kwargs):
        try:
            outp = req_function(request, *args, **kwargs)
            if issubclass(outp.__class__, HttpResponse):
                response = outp
            else:
                response = HttpResponse()
                response.write('%s' % json.dumps(outp))
                response['Content-length'] = str(len(response.content))

            response['Content-Type'] = "application/json"

        except HttpBadRequestException, bad_request:
            response = HttpResponseBadRequest(bad_request.message)

        return response
    return newreq

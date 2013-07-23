import json

from functools import wraps

from django.template import RequestContext
from django.shortcuts import get_object_or_404, render_to_response
from django.http import HttpResponse, HttpResponseBadRequest

from treemap.models import Instance


class HttpBadRequestException(Exception):
    pass


class InvalidInstanceException(Exception):
    pass


def instance_request(view_fn):
    @wraps(view_fn)
    def wrapper(request, instance_id, *args, **kwargs):
        instance = get_object_or_404(Instance, pk=instance_id)
        # Include the instance as both a request property and as an
        # view function argument for flexibility and to keep "template
        # only" requests simple.
        request.instance = instance
        return view_fn(request, instance, *args, **kwargs)

    return wrapper


def strip_request(view_fn):
    @wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        return view_fn(*args, **kwargs)

    return wrapper


def render_template(templ, view_fn_or_dict=None, **kwargs):
    def wrapper(request, *args, **wrapper_kwargs):
        if view_fn_or_dict is None:
            params = None
        elif type(view_fn_or_dict) is dict:
            params = view_fn_or_dict
        else:
            params = view_fn_or_dict(request, *args, **wrapper_kwargs)

        return render_to_response(templ, params,
                                  RequestContext(request), **kwargs)
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

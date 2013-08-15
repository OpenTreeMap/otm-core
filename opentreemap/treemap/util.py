import json
import datetime
from collections import OrderedDict

from functools import wraps
from urlparse import urlparse
from django.template import RequestContext
from django.shortcuts import get_object_or_404, render_to_response, resolve_url
from django.http import (HttpResponse, HttpResponseBadRequest,
                         HttpResponseRedirect)
from django.utils.encoding import force_str
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.conf import settings
from django.core.urlresolvers import reverse

from treemap.models import Instance


class HttpBadRequestException(Exception):
    pass


class InvalidInstanceException(Exception):
    pass


def store_visited_instance(request, instance):
    last_instances = request.session.get('last_instances', OrderedDict())

    if instance.pk in last_instances:
        del last_instances[instance.pk]
    last_instances[instance.pk] = datetime.datetime.now()

    request.session['last_instances'] = last_instances
    request.session.modified = True


def get_last_instance(request):
    if 'last_instances' in request.session:
        instance_id = next(reversed(request.session['last_instances']))
        return Instance.objects.get(pk=instance_id)
    else:
        return None


def login_redirect(request):
    # Reference: django/contrib/auth/decorators.py
    path = request.build_absolute_uri()
    # urlparse chokes on lazy objects in Python 3, force to str
    resolved_login_url = force_str(
        resolve_url(settings.LOGIN_URL))
    # If the login url is the same scheme and net location then just
    # use the path as the "next" url.
    login_scheme, login_netloc = urlparse(resolved_login_url)[:2]
    current_scheme, current_netloc = urlparse(path)[:2]
    if (not login_scheme or login_scheme == current_scheme)\
    and (not login_netloc or login_netloc == current_netloc):  # NOQA
        path = request.get_full_path()
    from django.contrib.auth.views import redirect_to_login
    return redirect_to_login(
        path, resolved_login_url, REDIRECT_FIELD_NAME)


def instance_request(view_fn):
    @wraps(view_fn)
    def wrapper(request, instance_id, *args, **kwargs):
        instance = get_object_or_404(Instance, pk=instance_id)
        # Include the instance as both a request property and as an
        # view function argument for flexibility and to keep "template
        # only" requests simple.
        request.instance = instance
        if instance.is_accessible_by(request.user):
            store_visited_instance(request, instance)
            return view_fn(request, instance, *args, **kwargs)
        else:
            if request.user.is_authenticated():
                return HttpResponseRedirect(reverse('instance_not_available'))
            else:
                return login_redirect(request)

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

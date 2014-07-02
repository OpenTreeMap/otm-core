# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
from functools import wraps

from django.core.exceptions import PermissionDenied
from django.template import RequestContext
from django.shortcuts import get_object_or_404, render_to_response
from django.http import (HttpResponse, HttpResponseBadRequest,
                         HttpResponseRedirect, HttpResponseForbidden)
from django.core.urlresolvers import reverse
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from treemap.util import (LazyEncoder, add_visited_instance,
                          get_instance_or_404, login_redirect)
from treemap.exceptions import (FeatureNotEnabledException,
                                HttpBadRequestException)


def instance_request(view_fn, redirect=True):
    @wraps(view_fn)
    def wrapper(request, instance_url_name, *args, **kwargs):
        instance = get_instance_or_404(url_name=instance_url_name)
        # Include the instance as both a request property and as an
        # view function argument for flexibility and to keep "template
        # only" requests simple.
        request.instance = instance

        request.instance_supports_ecobenefits = instance.has_itree_region()

        user = request.user
        if user.is_authenticated():
            instance_user = user.get_instance_user(instance)
            request.instance_user = instance_user

        if instance.is_accessible_by(request.user):
            add_visited_instance(request, instance)
            return view_fn(request, instance, *args, **kwargs)
        else:
            if redirect:
                if request.user.is_authenticated():
                    return HttpResponseRedirect(
                        reverse('instance_not_available'))
                else:
                    return login_redirect(request)
            else:
                return HttpResponse('Unauthorized', status=401)

    return wrapper


def log(message=None):
    """Log a message before passing through to the wrapped function.

    This is useful if you want to determine whether wrappers are
    passing down the pipeline to the functions they wrap, or exiting
    early, usually with some kind of exception.

    Example:
    example_view = do(instance_request,
                      log("instance_request passed"),
                      json_api_call,
                      example)
    """
    def decorator(view_fn):
        @wraps(view_fn)
        def f(*args, **kwargs):
            print(message)
            return view_fn(*args, **kwargs)
        return f
    return decorator


def user_must_be_admin(view_fn):
    @wraps(view_fn)
    def f(request, instance, *args, **kwargs):
        user = request.user

        if user.is_authenticated():
            user_instance = user.get_instance_user(instance)

            if user_instance and user_instance.admin:
                return view_fn(request, instance, *args, **kwargs)

        raise PermissionDenied

    return f


def admin_instance_request(view_fn, redirect=True):
    return login_required(instance_request(
        user_must_be_admin(view_fn), redirect))


def api_admin_instance_request(view_fn):
    return admin_instance_request(view_fn, redirect=False)


def api_instance_request(view_fn):
    return instance_request(view_fn, redirect=False)


def strip_request(view_fn):
    """
    takes a regular function and modifies it to take a request as its first arg

    useful for taking a plain python function and promoting it to a view, in
    the case where it will only need access to the args provided by url params
    or other wrapping function.

    for example, with function:
    fn = lambda foo, bar: foo + bar

    url r'treemap/(?P<foo>)/(?P<bar>)/' can map to the view function
    returned by strip_request(fn)
    """
    @wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        return view_fn(*args, **kwargs)

    return wrapper


def require_http_method(method):
    return require_http_methods([method])


def requires_feature(ft):
    def wrapper_function(view_fn):
        @wraps(view_fn)
        def wrapped(request, instance, *args, **kwargs):
            if instance.feature_enabled(ft):
                return view_fn(request, instance, *args, **kwargs)
            else:
                raise FeatureNotEnabledException('Feature Not Enabled')

        return wrapped

    return wrapper_function


def render_template(template):
    """
    takes a template to render to and returns a function that
    takes an object to render the data for this template.

    If callable_or_dict is callable, it will be called with
    the request and any additional arguments to produce the
    template paramaters. This is useful for a view-like function
    that returns a dict-like object instead of an HttpResponse.

    Otherwise, callable_or_dict is used as the parameters for
    the rendered response.
    """
    def outer_wrapper(callable_or_dict=None, statuscode=None, **kwargs):
        def wrapper(request, *args, **wrapper_kwargs):
            if callable(callable_or_dict):
                params = callable_or_dict(request, *args, **wrapper_kwargs)
            else:
                params = callable_or_dict

            # If we want to return some other response
            # type we can, that simply overrides the default
            # behavior
            if params is None or isinstance(params, dict):
                resp = render_to_response(template, params,
                                          RequestContext(request), **kwargs)
            else:
                resp = params

            if statuscode:
                resp.status_code = statuscode

            return resp

        return wrapper
    return outer_wrapper


def json_api_call(req_function):
    """ Wrap a view-like function that returns an object that
        is convertable from json
    """
    @wraps(req_function)
    def newreq(request, *args, **kwargs):
        outp = req_function(request, *args, **kwargs)
        if issubclass(outp.__class__, HttpResponse):
            return outp
        else:
            return '%s' % json.dumps(outp, cls=LazyEncoder)
    return string_to_response("application/json")(newreq)


def string_to_response(content_type):
    """
    Wrap a view-like function that returns a string and marshalls it into an
    HttpResponse with the given Content-Type
    """
    def outer_wrapper(req_function):
        @wraps(req_function)
        def newreq(request, *args, **kwargs):
            try:
                outp = req_function(request, *args, **kwargs)
                if issubclass(outp.__class__, HttpResponse):
                    response = outp
                else:
                    response = HttpResponse()
                    response.write(outp)
                    response['Content-length'] = str(len(response.content))

                response['Content-Type'] = content_type

            except HttpBadRequestException, bad_request:
                response = HttpResponseBadRequest(bad_request.message)

            return response
        return newreq
    return outer_wrapper


def return_400_if_validation_errors(req):
    @wraps(req)
    def run_and_catch_validations(*args, **kwargs):
        try:
            return req(*args, **kwargs)
        except ValidationError as e:
            if hasattr(e, 'message_dict'):
                message_dict = e.message_dict
            else:
                message_dict = {'errors': e.messages}

            return HttpResponseBadRequest(
                json.dumps(message_dict, cls=LazyEncoder))

    return run_and_catch_validations


def login_or_401(view_fn):
    """
    A function decorator that works similarly to Django's login_required,
    except instead of redirecting to a login page, it returns an unauthorized
    status code.
    Intended for AJAX endpoints where it would not make sense to redirect
    """
    @wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated():
            return view_fn(request, *args, **kwargs)
        else:
            return HttpResponse('Unauthorized', status=401)

    return wrapper


def username_matches_request_user(view_fn):
    """
    A decorator intended for use on any feature gated in the template by
    {% userccontent for request.user %}.  Checks if the username matches the
    request user, and if so replaces username with the actual user object.
    Returns 404 if the username does not exist, and 403 if it doesn't match.
    """
    @wraps(view_fn)
    def wrapper(request, username, *args, **kwargs):
        # Delayed import because models imports from util
        from treemap.models import User

        user = get_object_or_404(User, username=username)
        if user != request.user:
            return HttpResponseForbidden()
        else:
            return view_fn(request, user, *args, **kwargs)

    return wrapper


def creates_instance_user(view_fn):
    @wraps(view_fn)
    def wrapper(request, instance, *args, **kwargs):
        # When I placed this import up top I got a AUTH_USER_MODEL error,
        # which usually implies there an issue loading and validating models.
        # Putting it here fixed it.
        from treemap.models import InstanceUser

        if request.user.get_instance_user(instance) is None:
            if instance.feature_enabled('auto_add_instance_user'):
                InstanceUser(
                    instance=instance,
                    user=request.user,
                    role=instance.default_role
                ).save_with_user(request.user)
            else:
                raise FeatureNotEnabledException(
                    'Users cannot join this map automatically')

        return view_fn(request, instance, *args, **kwargs)

    return wrapper


class classproperty(property):
    def __get__(self, cls, owner):
        return classmethod(self.fget).__get__(None, owner)()

# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
from functools import wraps

from django.utils.translation import ugettext as _
from django.core.exceptions import PermissionDenied
from django.http import (HttpResponse, HttpResponseBadRequest,
                         HttpResponseRedirect)
from django.core.urlresolvers import reverse
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from django_tinsel.utils import LazyEncoder, decorate as do
from django_tinsel.decorators import json_api_call

from opentreemap.util import request_is_embedded

from treemap.util import (add_visited_instance,
                          get_instance_or_404, login_redirect,
                          can_read_as_super_admin)


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
                if request_is_embedded(request):
                    return HttpResponseRedirect(
                        reverse('instance_not_available') + '?embed=1')
                elif request.user.is_authenticated():
                    return HttpResponseRedirect(
                        reverse('instance_not_available'))
                else:
                    return login_redirect(request)
            else:
                return HttpResponse('Unauthorized', status=401)

    return wrapper


def user_must_be_admin(view_fn):
    @wraps(view_fn)
    def f(request, instance, *args, **kwargs):
        user = request.user

        if user.is_authenticated():
            user_instance = user.get_instance_user(instance)
            is_admin = user_instance and user_instance.admin

            if is_admin or can_read_as_super_admin(request):
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
                raise PermissionDenied

        return wrapped

    return wrapper_function


def requires_permission(codename):
    """
    Wraps view function, testing whether the current user has the
    specified permission.
    """
    def wrapper_function(view_fn):
        @wraps(view_fn)
        def wrapped(request, instance, *args, **kwargs):
            from treemap.audit import Role
            role = Role.objects.get_role(instance, request.user)
            if role.has_permission(codename):
                return view_fn(request, instance, *args, **kwargs)
            else:
                raise PermissionDenied

        return wrapped

    return wrapper_function


def json_api_edit(req_function):
    """
    Wraps view function for an AJAX call which modifies data.
    """
    return do(
        login_or_401,
        json_api_call,
        creates_instance_user,
        req_function)


def return_400_if_validation_errors(req):
    @wraps(req)
    def run_and_catch_validations(*args, **kwargs):
        message_dict = {}
        try:
            return req(*args, **kwargs)
        except ValidationError as e:
            if hasattr(e, 'message_dict'):
                message_dict['globalErrors'] = [_(
                    'One or more of the specified values are invalid.')]
                if 'globalErrors' in e.message_dict:
                    message_dict['globalErrors'] += \
                        e.message_dict.pop('globalErrors')
                message_dict['fieldErrors'] = e.message_dict
            else:
                message_dict['globalErrors'] = e.messages

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


def creates_instance_user(view_fn):
    @wraps(view_fn)
    def wrapper(request, instance, *args, **kwargs):
        # prevent circular imports
        from treemap.models import InstanceUser

        if request.user.get_instance_user(instance) is None:
            if instance.feature_enabled('auto_add_instance_user'):
                InstanceUser(
                    instance=instance,
                    user=request.user,
                    role=instance.default_role
                ).save_with_user(request.user)
            else:
                raise PermissionDenied

        return view_fn(request, instance, *args, **kwargs)

    return wrapper


class classproperty(property):
    def __get__(self, cls, owner):
        return classmethod(self.fget).__get__(None, owner)()

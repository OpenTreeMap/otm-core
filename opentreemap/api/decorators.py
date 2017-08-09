# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import datetime

from functools import wraps

from django.http import HttpResponseBadRequest
from django.contrib.auth.models import AnonymousUser

from django_tinsel.exceptions import HttpBadRequestException

from api.models import APIAccessCredential
from api.auth import (create_401unauthorized, get_signature_for_request,
                      parse_user_from_request)

SIG_TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%S'
API_VERSIONS = {2, 3, 4}


def check_signature_and_require_login(view_f):
    return _check_signature(view_f, require_login=True)


def check_signature(view_f):
    return _check_signature(view_f, require_login=False)


def _check_signature(view_f, require_login):
    _bad_request = HttpResponseBadRequest('Invalid signature')
    _missing_request = HttpResponseBadRequest('Missing signature or timestamp')

    @wraps(view_f)
    def wrapperf(request, *args, **kwargs):
        # Request must have signature and access_key
        # parameters
        sig = request.GET.get('signature')

        if not sig:
            sig = request.META.get('HTTP_X_SIGNATURE')

        if not sig:
            return _missing_request

        # Signature may have had "+" changed to spaces so change them
        # back
        sig = sig.replace(' ', '+')

        timestamp = request.GET.get('timestamp')
        if not timestamp:
            return _missing_request

        try:
            timestamp = datetime.datetime.strptime(
                timestamp, SIG_TIMESTAMP_FORMAT)

            expires = timestamp + datetime.timedelta(minutes=15)

            if expires < datetime.datetime.now():
                return _bad_request

        except ValueError:
            return _missing_request

        if not sig:
            return _missing_request

        key = request.GET.get('access_key')

        if not key:
            return _bad_request

        try:
            cred = APIAccessCredential.objects.get(access_key=key)
        except APIAccessCredential.DoesNotExist:
            return _bad_request

        if not cred.enabled:
            return create_401unauthorized()

        signed = get_signature_for_request(request, cred.secret_key)

        if len(signed) != len(sig):
            return _bad_request

        # Don't bail early
        matches = 0
        for (c1, c2) in zip(sig, signed):
            matches = (ord(c1) ^ ord(c2)) | matches

        if matches == 0:
            if cred.user:
                user = cred.user
            else:
                user = parse_user_from_request(request)

            if require_login:
                if user is None or user.is_anonymous():
                    return create_401unauthorized()

            if user is None:
                user = AnonymousUser()

            request.user = user
            return view_f(request, *args, **kwargs)

        else:
            return _bad_request

    return wrapperf


def login_required(view_f):
    @wraps(view_f)
    def wrapperf(request, *args, **kwargs):
        user = parse_user_from_request(request) or request.user

        if user is not None and not user.is_anonymous():
            request.user = user
            return view_f(request, *args, **kwargs)

        return create_401unauthorized()

    return wrapperf


def login_optional(view_f):
    @wraps(view_f)
    def wrapperf(request, *args, **kwargs):
        user = parse_user_from_request(request)

        if user is not None:
            request.user = user

        return view_f(request, *args, **kwargs)

    return wrapperf


def set_api_version(view_f):
    @wraps(view_f)
    def wrapper(request, version, *args, **kwargs):
        api_version = int(version)
        if api_version not in API_VERSIONS:
            raise HttpBadRequestException("Version %s is not supported"
                                          % version)

        request.api_version = api_version
        return view_f(request, *args, **kwargs)

    return wrapper

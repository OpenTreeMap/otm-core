# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import base64
import datetime
import hashlib
import hmac
import re
import urllib

from functools import wraps

from django.http import HttpResponse, HttpResponseBadRequest
from django.contrib.auth import authenticate
from django.contrib.auth.models import AnonymousUser

from api.models import APIAccessCredential

SIG_TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%S'


def get_signature_for_request(request, secret_key):
    """
    Generate a signature for the given request

    Based on AWS signatures:
    http://docs.aws.amazon.com/AmazonSimpleDB/latest/
    DeveloperGuide/HMACAuth.html
    """
    httpverb = request.method
    hostheader = request.META.get('HTTP_HOST', '').lower()

    request_uri = request.path

    params = sorted(request.REQUEST.iteritems(), key=lambda a: a[0])

    paramstr = '&'.join(['%s=%s' % (k, urllib.quote_plus(str(v)))
                         for (k, v) in params
                         if k.lower() != "signature"])

    sign_string = '\n'.join([httpverb, hostheader, request_uri, paramstr])

    # Sometimes reeading from body fails, so try reading as a file-like
    try:
        body_encoded = base64.b64encode(request.body)
    except:
        body_encoded = base64.b64encode(request.read())

    if body_encoded:
        sign_string += body_encoded

    sig = base64.b64encode(
        hmac.new(secret_key, sign_string, hashlib.sha256).digest())

    return sig


def create_401unauthorized(body="Unauthorized"):
    res = HttpResponse(body)
    res.status_code = 401
    res['WWW-Authenticate'] = 'Basic realm="Secure Area"'
    return res


def firstmatch(regx, strg):
    m = re.match(regx, strg)
    if m is None:
        return None
    else:
        return m.group(1)


def decodebasicauth(strg):
    if strg is None:
        return None
    else:
        m = re.match(r'([^:]*)\:(.*)', base64.decodestring(strg))
        if m is not None:
            return (m.group(1), m.group(2))
        else:
            return None


def parse_basicauth(authstr):
    auth = decodebasicauth(firstmatch('Basic (.*)', authstr))
    if auth is None:
        return None
    else:
        return authenticate(username=auth[0], password=auth[1])


def parse_user_from_request(request):
    user = None
    if 'HTTP_AUTHORIZATION' in request.META:
        auth = request.META['HTTP_AUTHORIZATION']
        user = parse_basicauth(auth)

    return user


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
        sig = request.REQUEST.get('signature')

        # Signature may have had "+" changed to spaces so change them
        # back
        sig = sig.replace(' ', '+')

        if not sig:
            sig = request.META.get('HTTP_X_SIGNATURE')

        timestamp = request.REQUEST.get('timestamp')
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

        key = request.REQUEST.get('access_key')

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

# -*- coding: utf-8 -*-


import base64
import hashlib
import hmac
import re
import urllib.request
import urllib.parse
import urllib.error

from django.http import HttpResponse, RawPostDataException
from django.contrib.auth import authenticate


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

    # This used to use request.REQUEST, but after some testing and analysis it
    # seems that both iOS & Android always pass named parameters in the query
    # string, even for non-GET requests
    params = sorted(iter(request.GET.items()), key=lambda a: a[0])

    paramstr = '&'.join(['%s=%s' % (k, urllib.parse.quote_plus(str(v)))
                         for (k, v) in params
                         if k.lower() != "signature"])

    sign_string = '\n'.join([httpverb, hostheader, request_uri, paramstr])

    # Sometimes reading from body fails, so try reading as a file-like object
    try:
        body_decoded = base64.b64encode(request.body).decode()
    except RawPostDataException:
        body_decoded = base64.b64encode(request.read()).decode()

    if body_decoded:
        sign_string += body_decoded

    try:
        binary_secret_key = secret_key.encode()
    except (AttributeError, UnicodeEncodeError):
        binary_secret_key = secret_key

    sig = base64.b64encode(
        hmac.new(
            binary_secret_key,
            sign_string.encode(),
            hashlib.sha256
        ).digest()
    )

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
    if strg is None or len(strg) == 0:
        return None
    else:
        m = re.match(r'([^:]*)\:(.*)', strg)
        if m is not None:
            return (m.group(1), m.group(2))
        else:
            return None


def parse_basicauth(authstr):
    parsed_binary_auth_as_string = firstmatch("Basic (.*)", authstr)
    if parsed_binary_auth_as_string is None:
        return None

    auth = decodebasicauth(parsed_binary_auth_as_string)
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

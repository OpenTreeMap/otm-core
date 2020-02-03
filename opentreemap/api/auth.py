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

    if sig is None:
        return sig

    return sig.decode()


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
    string_wrapped_binary_credentials = firstmatch("Basic (.*)", authstr)
    if string_wrapped_binary_credentials is None:
        return None

    # tease bytes-like object out of string, i.e. "b'credentials'"
    reg_exp = r"'(.*?)\'"
    parsed_credentials = re.search(r"'(.*?)\'", string_wrapped_binary_credentials)
    str_credentials = parsed_credentials.groups()[0]
    decoded_str_credentials = base64.decodebytes(
        bytes(str_credentials, 'utf-8')
    ).decode()
    auth = decodebasicauth(decoded_str_credentials)

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

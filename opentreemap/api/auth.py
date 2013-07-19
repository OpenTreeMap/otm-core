from django.http import HttpResponse
from django.contrib.auth import authenticate
import re
import base64
from functools import wraps

def create_401unauthorized(body="Unauthorized"):
    res = HttpResponse(body)
    res.status_code = 401
    res['WWW-Authenticate'] = 'Basic realm="Secure Area"'
    return res

def firstmatch(regx, strg):
    m = re.match(regx, strg)
    if (m == None):
        return None
    else:
        return m.group(1)

def decodebasicauth(strg):
    if (strg == None):
        return None
    else:
        m = re.match(r'([^:]*)\:(.*)', base64.decodestring(strg))
        if (m != None):
            return (m.group(1), m.group(2))
        else:
            return None

def parse_basicauth(authstr):
    auth = decodebasicauth(firstmatch('Basic (.*)', authstr))
    if (auth == None):
        return None
    else:
        return authenticate(username = auth[0], password = auth[1])
        
def parse_user_from_request(request):
    user = None
    if (request.META.has_key('HTTP_AUTHORIZATION')):
        auth = request.META['HTTP_AUTHORIZATION']
        user = parse_basicauth(auth)

    return user

def login_required(view_f):
    @wraps(view_f)
    def wrapperf(request, *args, **kwargs):
        user = parse_user_from_request(request)

        if (user != None):
            request.user = user
            return view_f(request, *args, **kwargs)

        return create_401unauthorized()

    return wrapperf

def login_optional(view_f):
    @wraps(view_f)
    def wrapperf(request, *args, **kwargs):
        user = parse_user_from_request(request)

        if (user != None):
            request.user = user

        return view_f(request, *args, **kwargs)

    return wrapperf

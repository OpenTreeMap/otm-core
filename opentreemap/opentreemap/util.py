# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json

from django.http import Http404


def route(**kwargs):
    """
    Route a request to different views based on http verb.

    Kwargs should be 'GET', 'POST', 'PUT', 'DELETE' or 'ELSE',
    where the first four map to a view to route to for that type of
    request method/verb, and 'ELSE' maps to a view to pass the request
    to if the given request method/verb was not specified.
    """
    def routed(request, *args2, **kwargs2):
        method = request.method
        if method in kwargs:
            req_method = kwargs[method]
            return req_method(request, *args2, **kwargs2)
        elif 'ELSE' in kwargs:
            return kwargs['ELSE'](request, *args2, **kwargs2)
        else:
            raise Http404()
    return routed


def decorate(*reversed_views):
    """
    provide a syntax decorating views without nested calls.

    instead of:
    instance_request(json_api_call(etag(<hash_fn>)(<view_fn>)))

    you can write:
    decorate(instance_request, json_api_call, etag(<hash_fn>), <view_fn>)
    """
    fns = reversed_views[::-1]
    view = fns[0]
    for wrapper in fns[1:]:
        view = wrapper(view)
    return view


def json_from_request(request):
    body = request.body

    if body:
        return json.loads(body)
    else:
        return None


def merge_view_contexts(viewfns):
    def wrapped(*args, **kwargs):
        context = {}
        for viewfn in viewfns:
            context.update(viewfn(*args, **kwargs))

        return context
    return wrapped


def dotted_split(string, item_count,
                 maxsplit=None,
                 failure_format_string="Malformed string: '%s'",
                 cls=Exception):
    """
    Split at period characters, validating
    that the number of splits is as it was intended
    by the caller.

    The normal str.split function in python does not
    provide validation, only a maxsplit, at which point
    it will stop. This function is more precise because
    it allows the callers to make guarantees about the
    number of returned values.
    """
    if maxsplit is not None:
        parts = string.split('.', maxsplit)
    else:
        parts = string.split('.')
    if len(parts) != item_count:
        raise cls(failure_format_string % string)
    else:
        return parts


def any_args_contain_pattern(args, patterns):
    for arg in args:
        for pattern in patterns:
            if arg.find(pattern) >= 0:
                return True
    else:
        return False


def dict_pop(dictionary, query):
    if query in dictionary:
        match = dictionary[query]
        del dictionary[query]
        return (match, True)
    else:
        return (None, False)


def force_obj_to_pk(obj):
    """
    A utility function for safely forcing a foreign-key/related object to
    its primary key, for comparison purposes.

    Django uses polymorphism in the ORM and model api to allow pks to stand
    in for bonafide object, and vice versa. Consequently, it's easy to lose
    track of what type the objects and scope are instances of. This becomes
    a problem when *comparison* happens, Because comparing a primary key to
    a model with that primary key does not return True, as expected.

    Example:
    foo = Tree.objects.all()[0]
    bar = Tree.objects.all()[0].pk
    assert(foo != bar)
    assert(force_obj_to_pk(foo) == force_obj_to_pk(bar))
    """
    if obj is None:
        return None
    elif hasattr(obj, 'pk'):
        return obj.pk
    elif hasattr(obj, 'id'):
        return obj.id
    else:
        return obj

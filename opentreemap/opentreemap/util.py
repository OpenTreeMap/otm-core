# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
import logging

from rollbar.logger import RollbarHandler

from django.conf import settings


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

    Note that this function was written to deal with an insidious issue found
    in django at the time of writing: sometimes `model.value_from_object` is
    and integer and sometimes it is the related object itself and it was not
    apparent after a source audit how to deduce what this value actually is
    at a given point in a model's lifecycle.
    """
    if obj is None:
        return None
    elif hasattr(obj, 'pk'):
        return obj.pk
    elif hasattr(obj, 'id'):
        return obj.id
    else:
        return obj


def get_ids_from_request(request):
    # Check both the POST & GET dictionaries
    ids_string = request.POST.get('ids', request.GET.get('ids', None))
    if ids_string:
        return [int(id) for id in ids_string.split(',')]
    else:
        return []


def add_rollbar_handler(logger, level=logging.WARNING):
    if settings.ROLLBAR_SERVER_ACCESS_TOKEN is not None:
        rollbar_handler = RollbarHandler()
        rollbar_handler.setLevel(level)
        logger.addHandler(rollbar_handler)


def extent_as_json(extent):
    xmin, ymin, xmax, ymax = extent

    return json.dumps({'xmin': xmin, 'ymin': ymin, 'xmax': xmax, 'ymax': ymax})


def extent_intersection(*extents):
    extents = zip(*extents)
    xmins, ymins, xmaxes, ymaxes = extents
    return (max(xmins), max(ymins), min(xmaxes), min(ymaxes))


def request_is_embedded(request):
    embed_value = None
    try:
        embed_value = request.GET.get('embed')
    except:
        pass
    return embed_value is not None and 0 < len(embed_value)

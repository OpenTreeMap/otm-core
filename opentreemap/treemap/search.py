# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from json import loads
from datetime import datetime

from django.db.models import Q

from django.contrib.gis.measure import Distance
from django.contrib.gis.geos import Point

from treemap.models import Plot, Boundary, Tree
from treemap.udf import DATETIME_FORMAT


class ParseException (Exception):
    def __init__(self, message):
        super(Exception, self).__init__(message)
        self.message = message


PLOT_MAPPING = {'plot': '',
                'tree': 'tree__',
                'species': 'tree__species__',
                'treePhoto': 'tree__treephoto__',
                'mapFeature': ''}

TREE_MAPPING = {'plot': 'plot__',
                'tree': '',
                'species': 'species__',
                'treePhoto': 'treephoto__',
                'mapFeature': 'plot__'}


class Filter(object):
    def __init__(self, filterstr, instance):
        self.filterstr = filterstr
        self.instance = instance

    def get_objects(self, ModelClass):
        if ModelClass == Tree:
            mapping = TREE_MAPPING
        else:
            mapping = DEFAULT_MAPPING

        q = create_filter(self.instance, self.filterstr, mapping)
            queryset = ModelClass.objects.filter(q)

        return queryset

    def get_object_count(self, ModelClass):
        return self.get_objects(ModelClass).count()

def create_filter(instance, filterstr, mapping):
    """
    A filter is a string that must be valid json and conform to
    the following grammar:
    literal        = json literal | GMT date string in 'YYYY-MM-DD HH:MM:SS'
    model          = 'plot' | 'tree' | 'species'
    value-property = 'MIN'
                   | 'MAX'
                   | 'EXCLUSIVE'
                   | 'IN'
                   | 'IS'
                   | 'WITHIN_RADIUS'
                   | 'IN_BOUNDARY'
                   | 'LIKE'
                   | 'ISNULL'
    combinator     = 'AND' | 'OR'
    predicate      = { model.field: literal }
                   | { model.field: { (value-property: literal)* }}
    filter         = predicate
                   | [combinator, filter*, literal?]

    mapping allows for the developer to search focussed on a
    particular object group

    Returns a Q object that can be applied to a model of your choice
    """
    if filterstr is not None and filterstr != '':
        query = loads(filterstr)
        q = _parse_filter(query, mapping)
    else:
        return base.objects.all()

    return q


def _parse_filter(query, mapping):
    if type(query) is dict:
        return _parse_predicate(query, mapping)
    elif type(query) is list:
        predicates = [_parse_filter(p, mapping) for p in query[1:]]
        return _apply_combinator(query[0], predicates)


def _parse_predicate(query, mapping):
    qs = [_parse_predicate_pair(*kv, mapping=mapping)
          for kv in query.iteritems()]
    return _apply_combinator('AND', qs)


def _parse_predicate_key(key, mapping):
    parts = key.split('.')

    if len(parts) != 2:
        raise ParseException(
            'Keys must be in the form of "model.field", not "%s"' %
            key)

    model, field = parts

    if model not in mapping:
        raise ParseException(
            'Valid models are: %s, not "%s"' %
            (mapping.keys(), model))

    return mapping[model] + field


def _parse_value(value):
    """
    A value can be either:
    * A date
    * A literal
    * A list of other values
    """
    if type(value) is list:
        return [_parse_value(v) for v in value]

    try:
        return datetime.strptime(value, DATETIME_FORMAT)
    except (ValueError, TypeError):
        return value


def _parse_min_max_value_fn(operator):
    """
    returns a function that produces singleton
    dictionary of django operands for the given
    query operator.
    """

    def fn(predicate_value):
        # a min/max predicate can either take
        # a value or a dictionary that provides
        # a VALUE and EXCLUSIVE flag.
        if type(predicate_value) == dict:
            raw_value = predicate_value.get('VALUE')
            exclusive = predicate_value.get('EXCLUSIVE')
        else:
            raw_value = predicate_value
            exclusive = False

        if exclusive:
            key = operator
        else:
            # django use lt/lte and gt/gte
            # to handle inclusive/exclusive
            key = operator + 'e'

        value = _parse_value(raw_value)

        return {key: value}

    return fn


def _parse_within_radius_value(predicate_value):
    """
    buildup the geospatial value for the RHS of an
    on orm call and pair it with the LHS
    """
    radius = _parse_value(predicate_value['RADIUS'])
    x = _parse_value(predicate_value['POINT']['x'])
    y = _parse_value(predicate_value['POINT']['y'])
    point = Point(x, y, srid=3857)

    return {'__dwithin': (point, Distance(m=radius))}


def _parse_in_boundary(boundary_id):
    boundary = Boundary.objects.get(pk=boundary_id)
    return {'__contained': boundary.geom}


# a predicate_builder takes a value for the
# corresponding predicate type and returns
# a singleton dictionary with a mapping of
# predicate kwargs to pass to a Q object
PREDICATE_TYPES = {
    'MIN': {
        'combines_with': {'MAX'},
        'predicate_builder': _parse_min_max_value_fn('__gt'),
    },
    'MAX': {
        'combines_with': {'MIN'},
        'predicate_builder': _parse_min_max_value_fn('__lt'),
    },
    'IN': {
        'combines_with': set(),
        'predicate_builder': (lambda value: {'__in': value}),
    },
    'IS': {
        'combines_with': set(),
        'predicate_builder': (lambda value: {'': value})
    },
    'LIKE': {
        'combines_with': set(),
        'predicate_builder': (lambda value: {'__icontains': value})
    },
    'ISNULL': {
        'combines_with': set(),
        'predicate_builder': (lambda value: {'__isnull': value})
    },
    'WITHIN_RADIUS': {
        'combines_with': set(),
        'predicate_builder': _parse_within_radius_value,
    },
    'IN_BOUNDARY': {
        'combines_with': set(),
        'predicate_builder': _parse_in_boundary
    }
}


def _parse_dict_value(valuesdict):
    """
    Loops over the keys provided and returns predicate pairs
    if all the keys validate.

    Supported keys are:
    'MIN', 'MAX', 'IN', 'IS', 'WITHIN_RADIUS'

    The following rules apply:
    IN, IS, WITHIN_RADIUS, and MIN/MAX (together) are mutually exclusive
    """

    params = {}

    for value_key in valuesdict:
        if value_key not in PREDICATE_TYPES:
            raise ParseException(
                'Invalid key: %s in %s' % (value_key, valuesdict))
        else:
            predicate_props = PREDICATE_TYPES[value_key]
            valid_values = predicate_props['combines_with'].union({value_key})
            if not valid_values.issuperset(set(valuesdict.keys())):
                raise ParseException(
                    'Cannot use these keys together: %s in %s' %
                    (valuesdict.keys(), valuesdict))
            else:
                predicate_builder = predicate_props['predicate_builder']
                param_pair = predicate_builder(valuesdict[value_key])
                params.update(param_pair)

    return params


def _parse_predicate_pair(key, value, mapping):
    search_key = _parse_predicate_key(key, mapping)
    if type(value) is dict:
        return Q(**{search_key + k: v
                    for (k, v)
                    in _parse_dict_value(value).iteritems()})
    else:
        return Q(**{search_key: value})


def _apply_combinator(combinator, predicates):
    """
    Apply the given combinator to the predicate list

    Supported combinators are currently 'AND' and 'OR'
    """
    if len(predicates) == 0:
        raise ParseException(
            'Empty predicate list is not allowed')

    q = predicates[0]
    if combinator == 'AND':
        for p in predicates[1:]:
            q = q & p

    elif combinator == 'OR':
        for p in predicates[1:]:
            q = q | p
    else:
        raise ParseException(
            'Only AND and OR combinators supported, not "%s"' %
            combinator)

    return q

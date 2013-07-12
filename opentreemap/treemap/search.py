from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from json import loads

from django.db.models import Q

from treemap.models import Plot

class ParseException (Exception):
    pass

MODEL_MAPPING = { 'plot': '',
                  'tree': 'tree__' }

def create_filter(filterstr):
    """
    A filter is a string that must be valid json and conform to
    the following grammar:
    literal        = json literal | GMT date string in 'YYYY-MM-DD HH:MM:SS'
    model          = 'plot' | 'tree'
    value-property = 'MIN' | 'MAX' | 'EXCLUSIVE' | 'IN' | 'IS'
    combinator     = 'AND' | 'OR'
    predicate      = { model.field: literal }
                   | { model.field: { (value-property: literal)* }}
    filter         = predicate
                   | [combinator, filter*]

    Returns a lazy query set of plot objects
    """
    query = loads(filterstr)

    q = _parse_filter(query)

    return Plot.objects.filter(q)

def _parse_filter(query):
    if type(query) is dict:
        return _parse_predicate(query)
    elif type(query) is list:
        predicates = [_parse_filter(p) for p in query[1:]]
        return _apply_combinator(query[0], predicates)

def _parse_predicate(query):
    qs = [_parse_predicate_pair(*kv) for kv in query.iteritems()]
    return _apply_combinator('AND', qs)

def _parse_predicate_key(key, mapping=MODEL_MAPPING):
    parts = key.split('.')

    if len(parts) != 2:
        raise ParseException, \
            'Keys must be in the form of "model.field", not "%s"' %\
            key

    model, field = parts

    if model not in mapping:
        raise ParseException, \
            'Valid models are: %s, not "%s"' %\
            (mapping.keys(), model)

    return mapping[model] + field


#TODO: Date not supported
def _parse_value(value):
    """
    A value can be either:
    * A date
    * A literal
    * A list of other values
    """
    if type(value) is list:
        return [_parse_value(v) for v in value]
    else:
        return value

def _parse_min_max_value(valuesdict):
    valid_keys = ['MIN', 'MAX', 'EXCLUSIVE']

    for key in valuesdict.keys():
        if key not in valid_keys:
            raise ParseException, 'Invalid value dict: %s' % valuesdict

    exclusive_sfx = ''

    if ('EXCLUSIVE' in valuesdict and
        valuesdict['EXCLUSIVE']):
        gt = '__gt'
        lt = '__lt'
    else:
        gt = '__gte'
        lt = '__lte'

    params = {}

    if 'MIN' in valuesdict:
        params[gt] = _parse_value(valuesdict['MIN'])

    if 'MAX' in valuesdict:
        params[lt] = _parse_value(valuesdict['MAX'])

    return params

def _parse_dict_value(valuesdict):
    """
    Supported keys are:
    'MIN', 'MAX', 'EXCLUSIVE', 'IN', 'IS'

    The following rules apply:
    IN, IS, and the MIN/MAX/EXCL are mutually exclusive

    EXCLUSIVE can only be specified with MIN and MAX
    """
    if 'MIN' in valuesdict or 'MAX' in valuesdict:
        return _parse_min_max_value(valuesdict)
    elif 'IN' in valuesdict:
        if len(valuesdict) != 1:
            raise ParseException, 'Invalid value dict: %s' % valuesdict

        return {'__in': _parse_value(valuesdict['IN'])}
    elif 'IS' in valuesdict:
        if len(valuesdict) != 1:
            raise ParseException, 'Invalid value dict: %s' % valuesdict

        return {'': _parse_value(valuesdict['IS'])}
    else:
        raise ParseException, 'Invalid value dict: %s' % valuesdict

def _parse_predicate_pair(key, value):
    search_key = _parse_predicate_key(key)
    if type(value) is dict:
        return Q(**{search_key + k: v for (k,v) in _parse_dict_value(value).iteritems()})
    else:
        return Q(**{search_key: value})


def _apply_combinator(combinator, predicates):
    """
    Apply the given combinator to the predicate list

    Supported combinators are currently 'AND' and 'OR'
    """
    if len(predicates) == 0:
        raise ParseException,\
            'Empty predicate list is not allowed'

    q = predicates[0]
    if combinator == 'AND':
        for p in predicates[1:]:
            q = q & p

    elif combinator == 'OR':
        for p in predicates[1:]:
            q = q | p
    else:
        raise ParseException,\
            'Only AND and OR combinators supported, not "%s"' %\
            combinator

    return q

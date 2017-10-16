# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from json import loads
from datetime import datetime
from functools import partial
from itertools import groupby, chain

from django.db.models import Q

from opentreemap.util import dotted_split

from treemap.lib.dates import DATETIME_FORMAT
from treemap.models import Boundary, Tree, Plot, Species, TreePhoto
from treemap.udf import UDFModel, UserDefinedCollectionValue
from treemap.units import storage_to_instance_units_factor
from treemap.util import to_object_name


class ParseException (Exception):
    def __init__(self, message):
        super(Exception, self).__init__(message)
        self.message = message


class ModelParseException(ParseException):
    pass


DEFAULT_MAPPING = {'plot': '',
                   'bioswale': '',
                   'rainGarden': '',
                   'rainBarrel': '',
                   'tree': 'tree__',
                   'species': 'tree__species__',
                   'treePhoto': 'tree__treephoto__',
                   'mapFeaturePhoto': 'mapfeaturephoto__',
                   'mapFeature': ''}

PLOT_RELATED_MODELS = {Plot, Tree, Species, TreePhoto}

MAP_FEATURE_RELATED_NAMES = {'mapFeature', 'mapFeaturePhoto'}


class Filter(object):
    def __repr__(self):
        return "(%s, %s)" % (self.filterstr, self.displaystr)

    def __init__(self, filterstr, displaystr, instance):
        self.filterstr = filterstr
        self.displaystr = displaystr
        self.display_filter = loads(displaystr) if displaystr else None
        self.instance = instance

    def get_objects(self, ModelClass):
        # Filter out invalid models
        model_name = ModelClass.__name__

        if not _model_in_display_filters(model_name, self.display_filter):
            return ModelClass.objects.none()

        q = create_filter(self.instance, self.filterstr, DEFAULT_MAPPING)
        if model_name == 'Plot':
            q = _apply_tree_display_filter(q, self.display_filter,
                                           DEFAULT_MAPPING)

        models = q.basekeys

        if _is_valid_models_list_for_model(models, model_name, ModelClass,
                                           self.instance):
            queryset = ModelClass.objects.filter(q)
        else:
            queryset = ModelClass.objects.none()

        return queryset

    def get_object_count(self, ModelClass):
        return self.get_objects(ModelClass).count()


def _is_valid_models_list_for_model(models, model_name, ModelClass, instance):
    """Validates everything in models are valid filters for model_name"""
    def collection_udf_set_for_model(Model):
        if not issubclass(ModelClass, UDFModel):
            return {}
        if hasattr(Model, 'instance'):
            fake_model = Model(instance=instance)
        else:
            fake_model = Model()
        return set(fake_model.collection_udfs_search_names())

    # MapFeature is valid for all models
    models = models - MAP_FEATURE_RELATED_NAMES

    object_name = to_object_name(model_name)
    models = models - {object_name}

    if model_name == 'Plot':
        related_models = PLOT_RELATED_MODELS
    else:
        related_models = {ModelClass}

    for Model in related_models:
        models = models - {to_object_name(Model.__name__)}
        if issubclass(Model, UDFModel):
            models = models - collection_udf_set_for_model(Model)

    return len(models) == 0


class FilterContext(Q):
    def __init__(self, *args, **kwargs):
        if 'basekey' in kwargs:
            self.basekeys = {kwargs['basekey']}

            del kwargs['basekey']
        else:
            self.basekeys = set()

        super(FilterContext, self).__init__(*args, **kwargs)

    def add(self, thing, conn):
        if thing.basekeys:
            self.basekeys = self.basekeys | thing.basekeys

        return super(FilterContext, self).add(thing, conn)


def convert_filter_units(instance, filter_dict):
    """
    Convert the values in a filter dictionary from display units to database
    units. Mutates the `filter_dict` argument and returns it.
    """
    for field_name, value in filter_dict.iteritems():
        if field_name not in ['tree.diameter', 'tree.height',
                              'tree.canopy_height', 'plot.width',
                              'plot.length', 'bioswale.drainage_area',
                              'rainBarrel.capacity',
                              'rainGarden.drainage_area']:
            continue

        model_name, field = dotted_split(field_name, 2, maxsplit=1)

        if isinstance(value, dict):
            factor = 1 / storage_to_instance_units_factor(instance,
                                                          model_name,
                                                          field)
            for k in ['MIN', 'MAX', 'IS']:
                if k in value:
                    try:
                        if isinstance(value[k], dict):
                            float_val = float(value[k]['VALUE'])
                            value[k]['VALUE'] = factor * float_val
                        else:
                            float_val = float(value[k])
                            value[k] = factor * float_val
                    except ValueError:
                        # If the value is non-numeric we can just leave is as
                        # is and let the filter logic handle it.
                        pass
    return filter_dict


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
        convert_filter_units(instance, query)
        q = _parse_filter(query, mapping)
    else:
        q = FilterContext()

    if instance:
        q = q & FilterContext(instance=instance)

    return q


def _parse_filter(query, mapping):
    if type(query) is dict:
        return _parse_query_dict(query, mapping)
    elif type(query) is list:
        predicates = [_parse_filter(p, mapping) for p in query[1:]]
        return _apply_combinator(query[0], predicates)


def _parse_query_dict(query_dict, mapping):
    # given a query_dict and a mapping similar to DEFAULT_MAPPING,
    # separate the collection udf queries from the scalar queries,
    # handle them distinctly, and then combine back together.

    # A search for {
    #    'udf:plot:<udfd>.action': ...,
    #    'udf.plot:<udfd>.date': ...}
    # should match IFF a plot with a UserDefinedCollectionValue
    # matches both the action and the date parts.
    # By corollary, it should NOT match a plot that has
    # one UserDefinedCollectionValue that matches the action,
    # and another that matches the date, neither of which matches both.
    by_type = _parse_by_is_collection_udf(query_dict, mapping)
    scalars = _unparse_scalars(by_type.pop('*', []))
    scalar_predicates = _parse_scalar_predicate(scalars, mapping) \
        if scalars else FilterContext()
    collection_predicates = _parse_collections(by_type, mapping) \
        if by_type else FilterContext()
    return _apply_combinator('AND', [scalar_predicates, collection_predicates])


def _parse_scalar_predicate(query, mapping):

    parse_dict_props = partial(_parse_dict_props_for_mapping, PREDICATE_TYPES)

    def parse_scalar_predicate_pair(key, value, mapping):
        model, prefix, search_key = _parse_predicate_key(key, mapping)

        if not isinstance(value, dict):
            query = {prefix + search_key: value}
        else:
            props_by_pred = parse_dict_props(value)

            query = {}

            for pred, props in props_by_pred.iteritems():

                lookup_tail, rhs = _parse_prop(props, value, pred, value[pred])

                cast = rhs if props['udf_cast'] else None

                lookup_key = _lookup_key(
                    prefix, search_key,
                    lookup_name=lookup_tail, cast=cast)

                query[lookup_key] = rhs

        return FilterContext(basekey=model, **query)

    qs = [parse_scalar_predicate_pair(*kv, mapping=mapping)
          for kv in query.iteritems()]
    return _apply_combinator('AND', qs)


def _parse_by_is_collection_udf(query_dict, mapping):
    '''
    given a `dict` query_dict mapping keys to individual predicates,
    and a mapping similar to DEFAULT_MAPPING,

    return a `dict` mapping keys to lists of queries for the key.

    The keys in the return `dict` are collection udf identifiers
    of the form  'udf:<model name>:<udfd>.<field name>', and
    '*' for all scalars, udf or otherwise.

    The values are lists of queries of the form: {
        'type': same as 'model' for collections, '*' for scalars,
        'model': the part of an identifier before the dot,
        'field': field name to be queried - 'id', possibly prefixed,
        'key': the original identifier,
        'value': a predicate `dict`
    }
    '''
    query_dict_list = [dict(value=v, **_parse_by_key_type(k, mapping=mapping))
                       for k, v in query_dict.items()]
    grouped = groupby(sorted(query_dict_list, key=lambda qd: qd['type']),
                      lambda qd: qd['type'])
    return {k: list(v) for k, v in grouped}


def _parse_by_key_type(key, mapping):
    '''
    given a string key, and a mapping similar to DEFAULT_MAPPING,
    return dict with keys 'type', 'model', 'field', 'key'.

    Collection UDF keys are returned as the dict 'type' value.

    Scalar keys, UDF or regular, return '*' as the dict 'type' value.
    '''
    model, prefix, field = _parse_predicate_key(key, mapping)
    typ = model if _is_udf(model) else '*'
    return {'type': typ, 'prefix': prefix, 'model': model,
            'field': field, 'key': key}


def _unparse_scalars(scalars):
    return dict(zip([qd['key'] for qd in scalars],
                    [qd['value'] for qd in scalars]))


def _parse_collections(by_type, mapping):
    '''
    given a `dict` keyed by collection identifiers,
    and a mapping similar to DEFAULT_MAPPING,

    return a `FilterContext` that ANDs together a `FilterContext`
    for each collection identifier.

    Each inner `FilterContext` represents a subquery on
    `UserDefinedCollectionValue`s for the `UserDefinedFieldDefinition`
    id in the collection identifier.
    '''
    def parse_collection_subquery(identifier, field_parts, mapping):
        # identifier looks like 'udf:<model type>:<udfd id>'
        __, model, udfd_id = identifier.split(':', 2)

        return FilterContext(
            basekey=model, **{
                mapping[model] + 'id__in': UserDefinedCollectionValue.objects
                .filter(_parse_udf_collection(udfd_id, field_parts))
                .values_list('model_id', flat=True)})

    return _apply_combinator(
        'AND', [parse_collection_subquery(identifier, field_parts, mapping)
                for identifier, field_parts in by_type.items()])


def _parse_udf_collection(udfd_id, query_parts):
    '''
    given a `UserDefinedFieldDefinition` id, and a list of `query_parts`,

    return a `FilterContext` that ANDs together `Q` queries intended
    to query the `UserDefinedCollectionValue` fields corresponding to
    the `UserDefinedFieldDefinition`.
    '''

    parse_udf_dict_value = partial(_parse_dict_value_for_mapping,
                                   COLLECTION_HSTORE_PREDICATE_TYPES)

    def parse_collection_udf_dict(key, value):
        __, field = _split_key(key)
        if isinstance(value, dict):
            preds = parse_udf_dict_value(value)
            query = {_lookup_key('data__', field, k):
                     v for (k, v) in preds.iteritems()}
        else:
            query = {_lookup_key('data__', field): value}
        return query

    return _apply_combinator(
        'AND', list(chain([Q(field_definition_id=udfd_id)],
                          [Q(**parse_collection_udf_dict(
                              part['key'], part['value']))
                           for part in query_parts])))


def _lookup_key(prefix, field, lookup_name='', cast=None):
    '''
    given a string prefix such as 'tree__' or 'data__',
    a custom field name such as 'Action', 'Date', or 'udf:Root Depth',
    an optional lookup_name such as '__lt' or '__contains',
    and an optional cast such as '__float',

    return a string lookup key.
    '''
    if _is_udf(field):
        field = _lookup_key('udfs__', field[4:])
        if isinstance(cast, float):
            cast = '__float'
        else:
            cast = ''
    else:
        cast = ''
    return '{}{}{}{}'.format(prefix, field, cast, lookup_name)


def _parse_predicate_key(key, mapping):
    '''
    given a key and a mapping,
    where key is a string, and mapping is similar to DEFAULT_MAPPING,
    return tuple(model_name, prefix, field_name)

    collection UDF search keys look like 'udf:<model>:<udfd>.<field>',
    yielding (<model>, mapping[<model>], <field>).

    A scalar UDF search key looks like '<model>.udf:<field>',
    yielding (<model>, mapping[<model>], udf:<field>).

    A regular field looks like '<model>.<field>',
    yielding (<model>, mapping[<model>], <field>).

    Raises `ParseException` if the key does not contain exactly one dot.
    Raises `ModelParseException` if the model part of the key is not found
    in the mapping argument.
    '''
    model, field = _split_key(key)

    if _is_udf(model):
        __, mapping_model, __ = model.split(':')
    else:
        mapping_model = model

    if mapping_model not in mapping:
        raise ModelParseException(
            'Valid models are: %s or a collection UDF, not "%s"' %
            (mapping.keys(), model))

    return model, mapping[mapping_model], field


def _split_key(key):
    format_string = 'Keys must be in the form of "model.field", not "%s"'

    return dotted_split(key, 2, failure_format_string=format_string,
                        cls=ParseException)


def _parse_value(value):
    """
    A value can be either:
    * A date
    * A literal
    * A list of other values
    """
    if type(value) is list:
        return [_parse_value(v) for v in value]

    # warning: order matters here, because datetimes
    # can actually parse into float values.
    try:
        return datetime.strptime(value, DATETIME_FORMAT)
    except (ValueError, TypeError):
        # TODO: Is this still a concern?
        #
        # We have do this because it is possible for postgres
        # to interpret numeric search values as integers when
        # they are actually being compared to hstore values stored
        # as floats. Since the hstore extension could cast the LHS to the
        # type of the RHS, it could fail to parse a string representation
        # of a float into an integer.
        try:
            return float(value)
        except ValueError:
            return value


def _parse_min_max_value_fn(operator, is_hstore=True):
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

        if is_hstore:
            if isinstance(value, datetime):
                value = value.date().isoformat()
            elif not isinstance(value, float):
                raise ParseException(
                    "Cannot perform min/max comparisons on "
                    "non-date/numeric hstore fields at this time.")

        return {key: value}

    return fn


def _parse_in_boundary(boundary_id):
    boundary = Boundary.all_objects.get(pk=boundary_id)
    return {'__within': boundary.geom}


def _simple_pred(key):
    return (lambda value: {key: value})


def _hstore_exact_predicate(val):
    return {'__exact': val}

# a predicate_builder takes a value for the
# corresponding predicate type and returns
# a singleton dictionary with a mapping of
# predicate kwargs to pass to a Q object
PREDICATE_TYPES = {
    'MIN': {
        'combines_with': {'MAX'},
        'udf_cast': True,
        'predicate_builder': _parse_min_max_value_fn('__gt'),
    },
    'MAX': {
        'combines_with': {'MIN'},
        'udf_cast': True,
        'predicate_builder': _parse_min_max_value_fn('__lt'),
    },
    'IN': {
        'combines_with': set(),
        'udf_cast': False,
        'predicate_builder': _simple_pred('__in'),
    },
    'IS': {
        'combines_with': set(),
        'udf_cast': False,
        'predicate_builder': _simple_pred('')
    },
    'LIKE': {
        'combines_with': set(),
        'udf_cast': False,
        'predicate_builder': _simple_pred('__icontains')
    },
    'ISNULL': {
        'combines_with': set(),
        'udf_cast': False,
        'predicate_builder': _simple_pred('__isnull')
    },
    'IN_BOUNDARY': {
        'combines_with': set(),
        'udf_cast': False,
        'predicate_builder': _parse_in_boundary
    }
}


COLLECTION_HSTORE_PREDICATE_TYPES = {
    'MIN': {
        'combines_with': {'MAX'},
        'udf_cast': False,
        'predicate_builder': _parse_min_max_value_fn('__gt', is_hstore=True),
    },
    'MAX': {
        'combines_with': {'MIN'},
        'udf_cast': False,
        'predicate_builder': _parse_min_max_value_fn('__lt', is_hstore=True),
    },
    'IS': {
        'combines_with': set(),
        'udf_cast': False,
        'predicate_builder': _hstore_exact_predicate,
    },
}


def _parse_dict_value_for_mapping(mapping, valuesdict):
    """
    given a mapping, valuesdict

    `mapping` is a dict mapping predicate types to rules.
    `valuesdict` maps predicate types to the values to search for.

    returns predicate pairs, if all the keys validate.

    Supported `mapping` and `valuesdict` keys are:
    'MIN', 'MAX', 'IN', 'IS', 'ISNULL', 'LIKE', 'IN_BOUNDARY'

    All predicates except MIN/MAX are mutually exclusive
    """

    props = _parse_dict_props_for_mapping(mapping, valuesdict)

    return _parse_props(props, valuesdict)


def _parse_props(props, valuesdict):

    params = {}

    for key, val in valuesdict.items():
        lookup, rhs = _parse_prop(props[key], valuesdict, key, val)
        params[lookup] = rhs

    return params


def _parse_prop(predicate_props, valuesdict, key, val):
        valid_values = predicate_props['combines_with'].union({key})
        if not valid_values.issuperset(set(valuesdict.keys())):
            raise ParseException(
                'Cannot use these keys together: %s vs %s' %
                (valuesdict.keys(), valid_values))

        predicate_builder = predicate_props['predicate_builder']
        param_pair = predicate_builder(val)
        # Return a 2-tuple rather than a single-key dict
        return param_pair.items()[0]


def _parse_dict_props_for_mapping(mapping, valuesdict):

    props = {}

    for value_key in valuesdict:
        if value_key not in mapping:
            raise ParseException(
                'Invalid key: %s in %s' % (value_key, valuesdict))
        else:
            props[value_key] = mapping[value_key]

    return props


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


def _model_in_display_filters(model_name, display_filters):
    if display_filters is not None:
        if model_name == 'Plot':
            plot_models = {'Plot', 'EmptyPlot', 'Tree'}
            return bool(plot_models.intersection(display_filters))
        else:
            return model_name in display_filters

    return True


def _apply_tree_display_filter(q, display_filter, mapping):
    if display_filter is not None:
        if 'Plot' in display_filter:
            return q

        is_empty_plot = 'EmptyPlot' in display_filter
        search_key = mapping['tree'] + 'pk__isnull'

        q = q & FilterContext(basekey='plot', **{search_key: is_empty_plot})

    return q


def _is_udf(name):
    return name.startswith('udf:')

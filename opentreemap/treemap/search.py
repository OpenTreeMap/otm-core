# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from json import loads
from datetime import datetime
from functools import partial
from itertools import groupby, chain

from django.db.models import Q

from django.contrib.gis.measure import Distance
from django.contrib.gis.geos import Point

from opentreemap.util import dotted_split

from treemap.lib.dates import DATETIME_FORMAT
from treemap.models import Boundary, Tree, Plot, Species, TreePhoto
from treemap.udf import UDFModel, UserDefinedCollectionValue
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
    # Separate the collection udf queries from the scalar queries,
    # handle them distinctly, and then combine back together.

    # A search for {
    #    'udf:plot:<udfd>.action': ...,
    #    'udf.plot:<udfd>.date': ...}
    # should match IFF a plot with a UserDefinedCollectionValue
    # matches both the action and the date parts.
    # By correlary, it should NOT match a plot that has
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
    qs = [_parse_scalar_predicate_pair(*kv, mapping=mapping)
          for kv in query.iteritems()]
    return _apply_combinator('AND', qs)


def _parse_by_is_collection_udf(query_dict, mapping):
    query_dict_list = [dict(value=v, **_parse_by_key_type(k, mapping=mapping))
                       for k, v in query_dict.items()]
    grouped = groupby(sorted(query_dict_list, key=lambda qd: qd['type']),
                      lambda qd: qd['type'])
    return {k: list(v) for k, v in grouped}


def _parse_by_key_type(key, mapping):
    model, field = _parse_predicate_key(key, mapping)
    typ = model if _is_udf(model) else '*'
    return {'type': typ, 'model': model, 'field': field, 'key': key}


def _unparse_scalars(scalars):
    return dict(zip([qd['key'] for qd in scalars],
                    [qd['value'] for qd in scalars]))


def _parse_collections(by_type, mapping):
    return _apply_combinator(
        'AND', [_parse_collection_subquery(identifier, field_parts, mapping)
                for identifier, field_parts in by_type.items()])


def _parse_collection_subquery(identifier, field_parts, mapping):
    # identifier looks like 'udf:<model type>:<udfd id>'
    __, model, udfd_id = identifier.split(':', 2)

    return FilterContext(
        basekey=model, **{
            mapping[model] + 'id__in': UserDefinedCollectionValue.objects
            .filter(_parse_udf_collection(udfd_id, field_parts))
            .values_list('model_id', flat=True)})


def _parse_udf_collection(udfd_id, query_parts):
    return _apply_combinator(
        'AND', list(chain([Q(field_definition=udfd_id)],
                          [Q(**_parse_udf_dict(part['key'], part['value']))
                           for part in query_parts])))


def _parse_predicate_key(key, mapping):
    format_string = 'Keys must be in the form of "model.field", not "%s"'
    model, field = dotted_split(key, 2,
                                failure_format_string=format_string,
                                cls=ParseException)

    if _is_udf(model):
        __, mapping_model, __ = model.split(':')
        field = 'id'
    else:
        mapping_model = model

    if mapping_model not in mapping:
        raise ModelParseException(
            'Valid models are: %s or a collection UDF, not "%s"' %
            (mapping.keys(), model))

    return model, mapping[mapping_model] + field


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
    # can actually actually parse into float values.
    try:
        return datetime.strptime(value, DATETIME_FORMAT)
    except (ValueError, TypeError):
        # We have do this because it is possible for postgres
        # to interpret numeric search values as integers when
        # they are actually being compared to hstore values stored
        # as floats. Since django-hstore will cast the LHS to the
        # type of the RHS, it fail to parse a string representation
        # of a float into an integer.
        #
        # TODO: submit a fix to django-hstore to handle this.
        try:
            return float(value)
        except ValueError:
            return value


def _parse_min_max_value_fn(operator):
    """
    returns a function that produces singleton
    dictionary of django operands for the given
    query operator.
    """

    def fn(predicate_value, field=None):
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

        if field:  # implies hstore
            if isinstance(value, datetime):
                date_value = value.date().isoformat()
                inner_value = {field: date_value}
            elif isinstance(value, float):
                inner_value = {field: value}
            else:
                raise ParseException(
                    "Cannot perform min/max comparisons on "
                    "non-date/numeric hstore fields at this time.")
        else:
            inner_value = value

        return {key: inner_value}

    return fn


def _parse_within_radius_value(predicate_value, field=None):
    """
    buildup the geospatial value for the RHS of an
    on orm call and pair it with the LHS
    """
    radius = _parse_value(predicate_value['RADIUS'])
    x = _parse_value(predicate_value['POINT']['x'])
    y = _parse_value(predicate_value['POINT']['y'])
    point = Point(x, y, srid=3857)

    return {'__dwithin': (point, Distance(m=radius))}


def _parse_in_boundary(boundary_id, field=None):
    boundary = Boundary.all_objects.get(pk=boundary_id)
    return {'__within': boundary.geom}


def _parse_isnull_hstore(value, field):
    if value:
        return {'__contains': {field: None}}
    return {'__contains': [field]}


def _simple_pred(key):
    return (lambda value, _: {key: value})


def _hstore_contains_predicate(val, field):
    """
    django_hstore builds different sql for the __contains predicate
    depending on whether the input value is a list or a single item
    so this works for both 'IN' and 'IS'
    """
    return {'__contains': {field: val}}

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
        'predicate_builder': _simple_pred('__in'),
    },
    'IS': {
        'combines_with': set(),
        'predicate_builder': _simple_pred('')
    },
    'LIKE': {
        'combines_with': set(),
        'predicate_builder': _simple_pred('__icontains')
    },
    'ISNULL': {
        'combines_with': set(),
        'predicate_builder': _simple_pred('__isnull')
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


HSTORE_PREDICATE_TYPES = {
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
        'predicate_builder': _hstore_contains_predicate,
    },
    'IS': {
        'combines_with': set(),
        'predicate_builder': _hstore_contains_predicate,
    },
    'ISNULL': {
        'combines_with': set(),
        'predicate_builder': _parse_isnull_hstore
    },
}


def _parse_dict_value_for_mapping(mapping, valuesdict, field=None):
    """
    Loops over the keys provided and returns predicate pairs
    if all the keys validate.

    Supported keys are:
    'MIN', 'MAX', 'IN', 'IS', 'WITHIN_RADIUS', 'IN_BOUNDARY'

    All predicates except MIN/MAX are mutually exclusive
    """

    params = {}

    for value_key in valuesdict:
        if value_key not in mapping:
            raise ParseException(
                'Invalid key: %s in %s' % (value_key, valuesdict))
        else:
            predicate_props = mapping[value_key]
            valid_values = predicate_props['combines_with'].union({value_key})
            if not valid_values.issuperset(set(valuesdict.keys())):
                raise ParseException(
                    'Cannot use these keys together: %s in %s' %
                    (valuesdict.keys(), valuesdict))
            else:
                predicate_builder = predicate_props['predicate_builder']
                param_pair = predicate_builder(valuesdict[value_key], field)
                params.update(param_pair)

    return params


_parse_dict_value = partial(_parse_dict_value_for_mapping, PREDICATE_TYPES)
_parse_udf_dict_value = partial(_parse_dict_value_for_mapping,
                                HSTORE_PREDICATE_TYPES)


def _parse_scalar_predicate_pair(key, value, mapping):
    try:
        model, search_key = _parse_predicate_key(key, mapping)
    except ModelParseException:
        raise

    query = {search_key + k: v for (k, v)
             in _parse_dict_value(value).iteritems()} \
        if isinstance(value, dict) \
        else {search_key: value}

    return FilterContext(basekey=model, **query)


def _parse_udf_dict(key, value):
    __, field = key.split('.')
    if isinstance(value, dict):
        preds = _parse_udf_dict_value(value, field)
        query = {'data' + k: v for (k, v) in preds.iteritems()}
    else:
        query = {'data__contains': {field: value}}
    return query


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


def _is_udf(model_name):
    return model_name.startswith('udf:')

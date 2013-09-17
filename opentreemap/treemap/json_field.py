from django.contrib.gis.db import models
from django.utils.six import with_metaclass

from south.modelsinspector import add_introspection_rules

import json


class JSONField(with_metaclass(models.SubfieldBase, models.TextField)):
    def to_python(self, value):
        if isinstance(value, basestring):
            return json.loads(value or "{}")
        else:
            return value

    def get_prep_value(self, value):
        return json.dumps(value or {})

    def get_prep_lookup(self, lookup_type, value):
        raise TypeError("JSONField doesn't support lookups")

add_introspection_rules([], ["^treemap\.instance\.JSONField"])


def is_json_field_reference(field_name):
    return '|' in field_name


def get_attr_from_json_field(model, field_name):
    """
    Get specified value from a JSON field.
    For example, if field_name is "config|foo", get the JSON
    field "config" from the model and look up the value "foo".
    Deeper lookups also work, e.g. "config|foo|bar|baz".
    Returns None if the JSON path is not found.
    """
    path = field_name.split('|')
    field = path[0]
    if not hasattr(model, field):
        raise ValueError('Model %s lacks field %s' % (model, field))
    else:
        val = getattr(model, field)
        for key in path[1:]:
            if not type(val) is dict:
                raise ValueError('Cannot get JSON path: %s' % field_name)
            val = val.get(key, {})
    if val == {}:
        val = None
    return val


def set_attr_on_json_field(model, field_name, value):
    """
    Set specified value on a JSON field (see get_attr_from_json_field)
    """
    path = field_name.split('|')
    field = path[0]
    if not hasattr(model, field):
        raise ValueError('Model %s lacks field %s' % (model, field))
    else:
        dictionary = getattr(model, field)
        if not type(dictionary) is dict:
            raise ValueError('Cannot set JSON path: %s' % field_name)
        for key in path[1:-1]:
            if not key in dictionary:
                dictionary[key] = {}
            dictionary = dictionary[key]
            if not type(dictionary) is dict:
                raise ValueError('Cannot set JSON path: %s' % field_name)
        dictionary[path[-1]] = value

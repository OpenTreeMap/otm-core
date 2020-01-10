# -*- coding: utf-8 -*-


# Helpers for building a JSON schema

string = {'type': 'string'}
number = {'type': 'number'}
num_list = {
    'type': 'array',
    'items': {'type': 'number', 'minimum': 0},
    'minItems': 1,
}


def obj(properties, optional_properties={}):
    return {
        'type': 'object',
        'additionalProperties': False,
        'required': list(properties.keys()),
        'properties':
        dict(list(properties.items()) + list(optional_properties.items()))
    }


def obj_list(properties, optional_properties={}):
    return {
        'type': 'array',
        'items': obj(properties, optional_properties)
    }


def make_schema(schema):
    schema['$schema'] = 'http://json-schema.org/draft-04/schema#'
    return schema

# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

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
        'required': properties.keys(),
        'properties': dict(properties.items() + optional_properties.items())
    }


def obj_list(properties, optional_properties={}):
    return {
        'type': 'array',
        'items': obj(properties, optional_properties)
    }


def make_schema(schema):
    schema['$schema'] = 'http://json-schema.org/draft-04/schema#'
    return schema

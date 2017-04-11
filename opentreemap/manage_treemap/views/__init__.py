# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.core.exceptions import ValidationError

from opentreemap.util import json_from_request, dotted_split
from treemap.json_field import is_json_field_reference, set_attr_on_json_field
from treemap.util import package_field_errors


def update_instance_fields_with_validator(validation_fn):
    def f(*args, **kwargs):
        kwargs['validation_fn'] = validation_fn
        return update_instance_fields(*args, **kwargs)

    return f


def update_instance_fields(request, instance, validation_fn=None):
    json_data = json_from_request(request)
    return _update_instance_fields(json_data, instance, validation_fn)


def _update_instance_fields(json_data, instance, validation_fn=None):
    error_dict = {}
    for identifier, value in json_data.iteritems():
        model, field_name = dotted_split(identifier, 2, maxsplit=1)

        obj = instance

        if validation_fn:
            errors = validation_fn(field_name, value, model)
            if errors is not None:
                error_dict[field_name] = errors

        if is_json_field_reference(field_name):
            set_attr_on_json_field(obj, field_name, value)
        else:
            setattr(obj, field_name, value)

    if error_dict:
        validation_error = ValidationError(error_dict)
    else:
        try:
            instance.save()
            return {'ok': True}
        except ValidationError, ve:
            validation_error = ve

    raise ValidationError(package_field_errors('instance', validation_error))

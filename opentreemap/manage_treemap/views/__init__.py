# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.core.exceptions import ValidationError

from opentreemap.util import json_from_request, dotted_split
from treemap.json_field import is_json_field_reference, set_attr_on_json_field
from treemap.plugin import validate_is_public
from treemap.util import package_field_errors


def update_instance_fields_with_validator(validation_fn):
    def f(*args, **kwargs):
        kwargs['validation_fn'] = validation_fn
        return update_instance_fields(*args, **kwargs)

    return f


def update_instance_fields(request, instance, validation_fn=None):
    json_data = json_from_request(request)
    # The update is a PUT request but the query string param appears in the GET
    # dict
    should_update_universal_rev = 'update_universal_rev' in request.GET
    return _update_instance_fields(json_data, instance, validation_fn,
                                   should_update_universal_rev)


def _update_instance_fields(json_data, instance, validation_fn=None,
                            should_update_universal_rev=False):
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
            validate_is_public(instance)
            instance.save()
            if should_update_universal_rev:
                instance.update_universal_rev()
            return {'ok': True}
        except ValidationError, ve:
            validation_error = ve

    raise ValidationError(package_field_errors('instance', validation_error))


def add_udf_notification(instance, udf_name):
    notifications = set(instance.config.get('udf_notifications', []))
    instance.config['udf_notifications'] = list(notifications | {udf_name})
    instance.save()


def remove_udf_notification(instance, udf_name):
    notifications = set(instance.config.get('udf_notifications', []))
    instance.config['udf_notifications'] = list(notifications - {udf_name})
    instance.save()

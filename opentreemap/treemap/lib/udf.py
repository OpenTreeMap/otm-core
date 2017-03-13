import json

from django.db import transaction

from treemap.audit import Role, FieldPermission, Authorizable
from treemap.udf import UserDefinedFieldDefinition, safe_get_udf_model_class
from treemap.util import to_object_name


def udf_exists(params, instance):
    """
    A little helper function to enable searching for a udf using
    the same syntax as udf_create.

    Unfortunately, udf_create is designed to read a dict of data
    that is quite different than the syntax you'd use for querying
    the UserDefinedFieldDefinition model directly.

    To make a more consistent API for the common case of first
    checking if a UDF exists using a data dict, and if not,
    creating it using the same API, this function exists.
    """
    data = _parse_params(params)

    # TODO: should use caching (udf_defs)
    udfs = UserDefinedFieldDefinition.objects.filter(
        instance=instance,
        model_type=data['model_type'],
        name=data['name'])

    return udfs.exists()


@transaction.atomic
def udf_create(params, instance):
    data = _parse_params(params)
    name, model_type, datatype = (data['name'], data['model_type'],
                                  data['datatype'])

    udf = UserDefinedFieldDefinition(
        name=name,
        model_type=model_type,
        iscollection=False,
        instance=instance,
        datatype=datatype)
    udf.save()

    Model = safe_get_udf_model_class(model_type)

    if issubclass(Model, Authorizable):
        field_name = udf.canonical_name
        _add_default_field_permissions(instance, model_type, field_name)

    _add_scalar_udf_to_field_configs(udf, instance)

    return udf


def _add_default_field_permissions(instance, model_type, field_name):
    """
    Add the default permission for this UDF to all roles in the instance.
    """
    for role in Role.objects.filter(instance=instance):
        FieldPermission.objects.get_or_create(
            model_name=model_type,
            field_name=field_name,
            permission_level=role.default_permission_level,
            role=role,
            instance=role.instance)


def _parse_params(params):
    name = params.get('udf.name', None)
    model_type = params.get('udf.model', None)
    udf_type = params.get('udf.type', None)

    datatype = {'type': udf_type}

    if udf_type in ('choice', 'multichoice'):
        datatype['choices'] = params.get('udf.choices', None)
        datatype['protected_choices'] = \
            params.get('udf.protected_choices', None)

    datatype = json.dumps(datatype)

    return {'name': name, 'model_type': model_type,
            'datatype': datatype}


def _add_scalar_udf_to_field_configs(udf, instance):
    save_instance = False

    for prop in ('mobile_api_fields', 'web_detail_fields'):
        attr = getattr(instance, prop)
        for group in attr:
            if (('model' in group and
                 group['model'] == to_object_name(udf.model_type))):
                field_keys = group.get('field_keys')

                if 'field_keys' in group and udf.full_name not in field_keys:
                    field_keys.append(udf.full_name)
                    save_instance = True
                    # The first time a udf is configured,
                    # getattr(instance, prop) returns a deepcopy of
                    # the default for prop.
                    # Mutating the deepcopy does not set prop on config
                    # to refer to that deepcopy, so we must do the
                    # setattr here.
                    setattr(instance, prop, attr)

    if save_instance:
        instance.save()

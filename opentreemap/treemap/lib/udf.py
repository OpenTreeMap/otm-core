import json

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _

from treemap.audit import Role, FieldPermission
from treemap.udf import (UserDefinedFieldDefinition)


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

    udfs = UserDefinedFieldDefinition.objects.filter(
        instance=instance,
        model_type=model_type,
        name=name)

    if udfs.exists():
        raise ValidationError(
            {'udf.name':
             [_("A user defined field with name "
                "'%(udf_name)s' already exists") % {'udf_name': name}]})

    if model_type not in {cls.__name__ for cls
                          in instance.editable_udf_models()}:
        raise ValidationError(
            {'udf.model': [_('Invalid model')]})

    udf = UserDefinedFieldDefinition(
        name=name,
        model_type=model_type,
        iscollection=False,
        instance=instance,
        datatype=datatype)
    udf.save()

    field_name = udf.canonical_name

    # Add a restrictive permission for this UDF to all roles in the
    # instance
    for role in Role.objects.filter(instance=instance):
        FieldPermission.objects.get_or_create(
            model_name=model_type,
            field_name=field_name,
            permission_level=FieldPermission.NONE,
            role=role,
            instance=role.instance)

    return udf


def _parse_params(params):
    name = params.get('udf.name', None)
    model_type = params.get('udf.model', None)
    udf_type = params.get('udf.type', None)

    datatype = {'type': udf_type}

    if udf_type in ('choice', 'multichoice'):
        datatype['choices'] = params.get('udf.choices', None)

    datatype = json.dumps(datatype)

    return {'name': name, 'model_type': model_type,
            'datatype': datatype}

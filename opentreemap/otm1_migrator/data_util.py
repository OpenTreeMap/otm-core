from treemap.audit import model_hasattr
from django.core.exceptions import ObjectDoesNotExist

import logging
logger = logging.getLogger('')


class MigrationException(Exception):
    pass


def validate_model_dict(config, model_name, data_hash):
    """
    Makes sure the fields specified in the config global
    account for all of the provided data
    """
    common_fields = config[model_name].get('common_fields', set())
    renamed_fields = set(config[model_name].get('renamed_fields', {}).keys())
    removed_fields = config[model_name].get('removed_fields', set())
    dependency_fields = set(config[model_name]
                            .get('dependencies', {}).values())
    undecided_fields = (config[model_name]
                        .get('undecided_fields', set()))
    expected_fields = (common_fields |
                       renamed_fields |
                       removed_fields |
                       undecided_fields |
                       dependency_fields)

    provided_fields = set(data_hash['fields'].keys())

    if expected_fields != provided_fields:
        raise Exception('model validation failure. \n\n'
                        'Expected: %s \n\n'
                        'Got: %s\n\n'
                        'Symmetric Difference: %s'
                        % (expected_fields, provided_fields,
                           expected_fields.
                           symmetric_difference(provided_fields)))


def hash_to_model(config, model_name, data_hash, instance):
    """
    Takes a model specified in the config global and a
    hash of json data and attempts to populate a django
    model. Does not save.
    """
    validate_model_dict(config, model_name, data_hash)

    common_fields = config[model_name].get('common_fields', set())
    renamed_fields = config[model_name].get('renamed_fields', {})
    dependency_fields = config[model_name].get('dependencies', {})

    model = config[model_name]['model_class']()

    identity = (lambda x: x)

    for field in (common_fields
                  .union(renamed_fields)
                  .union(dependency_fields.values())):
        transform_fn = (config[model_name]
                        .get('value_transformers', {})
                        .get(field, identity))

        transformed_value = transform_fn(data_hash['fields'][field])
        field = renamed_fields.get(field, field)
        if field in dependency_fields.values():
            field += '_id'

        setattr(model, field, transformed_value)

    if model_hasattr(model, 'instance'):
        model.instance = instance

    return model

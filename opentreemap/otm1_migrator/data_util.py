from treemap.models import User
from treemap.audit import model_hasattr

from treemap.util import to_model_name
from treemap.lib import udf as udf_lib


class MigrationException(Exception):
    pass


def validate_model_dict(config, model_name, data_dict):
    """
    Makes sure the fields specified in the config global
    account for all of the provided data
    """
    common_fields = config[model_name].get('common_fields', set())
    renamed_fields = set(config[model_name].get('renamed_fields', {}).keys())
    removed_fields = config[model_name].get('removed_fields', set())
    dependency_fields = set(config[model_name]
                            .get('dependencies', {}).values())
    expected_fields = (common_fields |
                       renamed_fields |
                       removed_fields |
                       dependency_fields)

    provided_fields = set(data_dict['fields'].keys())

    if expected_fields != provided_fields:
        raise Exception('model validation failure. \n\n'
                        'Expected: %s \n\n'
                        'Got: %s\n\n'
                        'Symmetric Difference: %s'
                        % (expected_fields, provided_fields,
                           expected_fields.
                           symmetric_difference(provided_fields)))


def dict_to_model(config, model_name, data_dict, instance):
    """
    Takes a model specified in the config global and a
    dict of json data and attempts to populate a django
    model. Does not save.
    """
    validate_model_dict(config, model_name, data_dict)

    common_fields = config[model_name].get('common_fields', set())
    renamed_fields = config[model_name].get('renamed_fields', {})
    dependency_fields = config[model_name].get('dependencies', {})

    model = config[model_name]['model_class']()

    # instance *must* be set before UDF assignment
    if model_hasattr(model, 'instance'):
        model.instance = instance

    for field in (common_fields
                  .union(renamed_fields)
                  .union(dependency_fields.values())):
        transform_fn = (config[model_name]
                        .get('value_transformers', {})
                        .get(field, None))

        transformed_value = (transform_fn(data_dict['fields'][field])
                             if transform_fn else data_dict['fields'][field])
        transformed_field = renamed_fields.get(field, field)

        if transformed_field.startswith('udf:'):
            if transformed_value is not None:
                model.udfs[transformed_field[4:]] = transformed_value
        else:
            suffix = ('_id'
                      if transformed_field in dependency_fields.values()
                      else '')
            setattr(model, transformed_field + suffix, transformed_value)

    for mutator in config[model_name].get('record_mutators', []):
        mutator(model, data_dict['fields'])

    return model


def uniquify_username(username):
    username_template = '%s_%%d' % username
    i = 0
    while User.objects.filter(username=username).exists():
        username = username_template % i
        i += 1

    return username


def sanitize_username(username):
    # yes, there was actually a user with newlines
    # in their username
    return (username
            .replace(' ', '_')
            .replace('\n', ''))


def add_udfs_to_migration_rules(migration_rules, udfs, instance):

    for model in udfs:
        model_rules = migration_rules[model]
        model_rules['removed_fields'] -= set(udfs[model].keys())

        for field, field_rules in udfs[model].items():
            prefixed = 'udf:' + field_rules['udf.name']
            model_rules['renamed_fields'][field] = prefixed

            conversions = {str(i+1): v for i, v in
                           enumerate(field_rules.get('udf.choices', []))}

            if conversions:
                value_transformers = model_rules.get(
                    'value_transformers', {})
                value_transformers[field] = conversions.get
                model_rules['value_transformers'] = value_transformers


def create_udfs(udfs, instance):
    for model, model_rules in udfs.items():
        for field, field_rules in model_rules.items():
            # convert the migrator udf schema
            # to the udf-lib friendly schema

            name = field_rules['udf.name']
            model_type = to_model_name(model)
            choices = field_rules.get('udf.choices')
            datatype_type = field_rules.get(
                'udf.type', 'choice' if choices else 'string')

            udf_params = {
                'udf.name': name,
                'udf.model': model_type,
                'udf.type': datatype_type,
                'udf.choices': choices
            }

            if not udf_lib.udf_exists(udf_params, instance):
                print "Creating udf %s" % name
                udf_lib.udf_create(udf_params, instance)

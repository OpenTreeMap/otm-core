# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from copy import deepcopy

from django.db import migrations

from treemap.DotDict import DotDict


identifier = u'plot.owner_orig_id'


def update_config_property(apps, update_fn, prop_name, *categories):
    Instance = apps.get_model("treemap", "Instance")
    filter_pattern = '\"{}\":'.format(prop_name)
    for instance in Instance.objects.filter(config__contains=filter_pattern):
        instance.config = update_fn(instance.config, prop_name, *categories)
        instance.save()


def is_in_values(specs, pattern):
    values = [spec.values() for spec in specs]
    return True in [pattern in v for v in values]


def add_to_config(config, prop_name, *categories):
    config = deepcopy(config or DotDict({}))
    for category in categories:
        lookup = '.'.join([prop_name, category])
        specs = config.setdefault(lookup, [])
        if not is_in_values(specs, identifier):
            # mutates config[lookup]
            specs.append({u'identifier': identifier})

    return config


def add_custom_id_forward(apps, schema_editor):
    update_config_property(apps, add_to_config, 'search_config',
                           'Plot', 'missing')
    update_config_property(apps, add_to_config, 'mobile_search_fields',
                           'standard', 'missing')


def remove_from_config(config, prop_name, *categories):
    config = deepcopy(config or DotDict({}))
    for category in categories:
        lookup = '.'.join([prop_name, category])
        specs = config.get(lookup)
        if specs:
            for index, spec in enumerate(specs):
                if identifier in spec.values():
                    break
            if index < len(specs):
                specs.pop(index)

    return config


def add_custom_id_backward(apps, schema_editor):
    update_config_property(apps, remove_from_config, 'search_config',
                           'Plot', 'missing')
    update_config_property(apps, remove_from_config, 'mobile_search_fields',
                           'standard', 'missing')


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0030_add_verbose_name_to_owner_orig_id'),
    ]

    operations = [
        migrations.RunPython(add_custom_id_forward, add_custom_id_backward),
    ]

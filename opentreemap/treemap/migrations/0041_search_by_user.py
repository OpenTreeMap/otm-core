# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from copy import deepcopy

from django.db import migrations

from treemap.DotDict import DotDict


identifier = u'mapFeature.updated_by'


def update_config_property(apps, update_fn, *categories):
    Instance = apps.get_model("treemap", "Instance")
    for instance in Instance.objects.filter(
            config__contains='\"search_config\":'):
        instance.config = update_fn(instance.config, *categories)
        instance.save()


def add_to_config(config, *categories):
    config = DotDict(deepcopy(config or {}))
    for category in categories:
        lookup = '.'.join(['search_config', category])
        specs = config.setdefault(lookup, [])
        if 0 == len([v for s in specs for v in s.values() if v == identifier]):
            # mutates config[lookup]
            specs.append({u'identifier': identifier})

    return config


def add_custom_id_forward(apps, schema_editor):
    update_config_property(apps, add_to_config, 'general')


def remove_from_config(config, *categories):
    config = DotDict(deepcopy(config or {}))
    for category in categories:
        lookup = '.'.join(['search_config', category])
        specs = config.get(lookup)
        if specs:
            find_index = [i for i, s in enumerate(specs)
                          if identifier in s.values()]
            if 0 < len(find_index):
                specs.pop(find_index[0])

    return config


def add_custom_id_backward(apps, schema_editor):
    update_config_property(apps, remove_from_config, 'general')


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0040_expand_itree_regions'),
    ]

    operations = [
        migrations.RunPython(add_custom_id_forward, add_custom_id_backward),
    ]

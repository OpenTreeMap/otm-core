# -*- coding: utf-8 -*-


from copy import deepcopy

from django.db import migrations

from treemap.DotDict import DotDict


identifier = 'plot.owner_orig_id'


def update_config_property(apps, update_fn, *categories):
    Instance = apps.get_model("treemap", "Instance")
    for instance in Instance.objects.filter(
            config__contains='\"search_config\":'):
        instance.config = update_fn(instance.config, *categories)
        instance.save()


def add_to_config(config, *categories):
    config = deepcopy(config or DotDict({}))
    for category in categories:
        lookup = '.'.join(['search_config', category])
        specs = config.setdefault(lookup, [])
        if True not in [identifier in v for s in specs for v in list(s.values())]:
            # mutates config[lookup]
            specs.append({'identifier': identifier})

    return config


def add_custom_id_forward(apps, schema_editor):
    update_config_property(apps, add_to_config, 'Plot', 'missing')


def remove_from_config(config, *categories):
    config = deepcopy(config or DotDict({}))
    for category in categories:
        lookup = '.'.join(['search_config', category])
        specs = config.get(lookup)
        if specs:
            for index, spec in enumerate(specs):
                if identifier in list(spec.values()):
                    break
            if index < len(specs):
                specs.pop(index)

    return config


def add_custom_id_backward(apps, schema_editor):
    update_config_property(apps, remove_from_config, 'Plot', 'missing')


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0030_add_verbose_name_to_owner_orig_id'),
    ]

    operations = [
        migrations.RunPython(add_custom_id_forward, add_custom_id_backward),
    ]

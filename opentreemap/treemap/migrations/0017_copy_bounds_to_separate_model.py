# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def copy_bounds_to_separate_model(apps, schema_editor):
    Instance = apps.get_model('treemap', 'Instance')
    InstanceBounds = apps.get_model('treemap', 'InstanceBounds')

    for instance in Instance.objects.all():
        ib = InstanceBounds(geom=instance.bounds)
        ib.save()
        instance.bounds_obj = ib
        instance.save()


def copy_separate_model_to_bounds(apps, schema_editor):
    Instance = apps.get_model('treemap', 'Instance')

    for instance in Instance.objects.all():
        ib = instance.bounds_obj
        instance.bounds = ib.geom
        instance.save()


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0016_make_bounds_nullable'),
    ]

    operations = [
        migrations.RunPython(copy_bounds_to_separate_model,
                             reverse_code=copy_separate_model_to_bounds)
    ]

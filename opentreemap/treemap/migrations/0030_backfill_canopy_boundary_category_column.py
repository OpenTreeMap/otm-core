# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def forward(apps, schema_editor):
    Instance = apps.get_model('treemap', 'Instance')
    db_alias = schema_editor.connection.alias
    Instance.objects.using(db_alias) \
        .filter(canopy_boundary_category__isnull=True) \
        .update(canopy_boundary_category='')


def reverse(apps, schema_editor):
    # Column is still non-null at this point so we can't assign a null value.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0026_add_canopy_fields'),
    ]

    run_before = [
        ('treemap', '0028_make_boundary_searchable_non_null'),
    ]

    operations = [
        migrations.RunPython(forward, reverse)
    ]

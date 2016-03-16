# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('importer', '0004_make_new_fields_nonnullable'),
    ]

    operations = [
        migrations.AddField(
            model_name='speciesimportevent',
            name='schema_version',
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='treeimportevent',
            name='schema_version',
            field=models.IntegerField(null=True, blank=True),
        ),
    ]

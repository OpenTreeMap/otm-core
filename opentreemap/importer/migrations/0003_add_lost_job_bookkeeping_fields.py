# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('importer', '0002_auto_20150630_1556'),
    ]

    operations = [
        migrations.AddField(
            model_name='speciesimportevent',
            name='is_lost',
            field=models.NullBooleanField(default=False),
        ),
        migrations.AddField(
            model_name='speciesimportevent',
            name='last_processed_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='treeimportevent',
            name='is_lost',
            field=models.NullBooleanField(default=False),
        ),
        migrations.AddField(
            model_name='treeimportevent',
            name='last_processed_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]

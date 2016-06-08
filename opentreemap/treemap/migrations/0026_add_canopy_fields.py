# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0025_remove_null_from_boundary_updated_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='boundary',
            name='canopy_percent',
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name='instance',
            name='canopy_boundary_category',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='instance',
            name='canopy_enabled',
            field=models.NullBooleanField(default=False),
        ),
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0026_add_canopy_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='instance',
            name='canopy_boundary_category',
            field=models.CharField(default='', max_length=255, blank=True),
        ),
        migrations.AlterField(
            model_name='instance',
            name='canopy_enabled',
            field=models.BooleanField(default=False),
        ),
    ]

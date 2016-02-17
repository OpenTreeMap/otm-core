# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0021_rename_bounds_obj_to_bounds'),
    ]

    operations = [
        migrations.AlterField(
            model_name='instance',
            name='basemap_type',
            field=models.CharField(default='google', max_length=255, choices=[('google', 'Google'), ('bing', 'Bing'), ('esri', 'ESRI'), ('tms', 'Tile Map Service')]),
        ),
    ]

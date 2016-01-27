# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.contrib.gis.db.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0015_add_separate_instance_bounds_model'),
    ]

    operations = [
        migrations.AlterField(
            model_name='instance',
            name='bounds',
            field=django.contrib.gis.db.models.fields.MultiPolygonField(srid=3857, null=True, blank=True),
        ),
    ]

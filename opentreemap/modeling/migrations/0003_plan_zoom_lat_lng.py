# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import treemap.json_field


class Migration(migrations.Migration):

    dependencies = [
        ('modeling', '0002_remove_plan_currentscenarioid'),
    ]

    operations = [
        migrations.AddField(
            model_name='plan',
            name='zoom_lat_lng',
            field=treemap.json_field.JSONField(null=True, blank=True),
        ),
    ]

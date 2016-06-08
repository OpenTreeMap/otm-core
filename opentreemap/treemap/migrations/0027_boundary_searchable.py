# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0026_add_canopy_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='boundary',
            name='searchable',
            field=models.NullBooleanField(default=True),
        ),
    ]

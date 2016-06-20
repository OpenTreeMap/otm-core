# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0027_boundary_searchable'),
    ]

    operations = [
        migrations.AlterField(
            model_name='boundary',
            name='searchable',
            field=models.BooleanField(default=True),
        ),
    ]

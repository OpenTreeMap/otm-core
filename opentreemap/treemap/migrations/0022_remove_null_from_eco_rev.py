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
            name='eco_rev',
            field=models.IntegerField(default=1),
        ),
    ]

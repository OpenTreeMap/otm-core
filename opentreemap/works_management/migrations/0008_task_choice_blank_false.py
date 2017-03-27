# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('works_management', '0007_merge'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='status',
            field=models.IntegerField(default=0, choices=[(0, 'Requested'), (1, 'Scheduled'), (2, 'Completed'), (3, 'Canceled')]),
        ),
    ]

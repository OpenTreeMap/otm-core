# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('works_management', '0006_task_priority'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='closed_on',
            field=models.DateField(null=True),
        ),
        migrations.AlterField(
            model_name='task',
            name='scheduled_on',
            field=models.DateField(null=True),
        ),
    ]

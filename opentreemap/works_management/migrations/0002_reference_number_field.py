# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('works_management', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='reference_number',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='workorder',
            name='reference_number',
            field=models.IntegerField(null=True),
        ),
    ]

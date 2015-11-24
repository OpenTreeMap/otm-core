# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stormwater', '0004_auto_20151021_1600'),
    ]

    operations = [
        migrations.AlterField(
            model_name='rainbarrel',
            name='capacity',
            field=models.FloatField(verbose_name='Capacity', error_messages={'invalid': 'Please enter a number.'}),
        ),
    ]

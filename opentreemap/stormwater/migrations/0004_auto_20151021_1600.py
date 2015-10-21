# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stormwater', '0003_rainbarrel'),
    ]

    operations = [
        migrations.AlterField(
            model_name='rainbarrel',
            name='capacity',
            field=models.FloatField(help_text='Capacity', error_messages={'invalid': 'Please enter a number.'}),
        ),
    ]

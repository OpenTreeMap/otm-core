# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0014_change_empty_multichoice_values'),
    ]

    operations = [
        migrations.AddField(
            model_name='instanceuser',
            name='last_seen',
            field=models.DateField(null=True, blank=True),
        ),
    ]

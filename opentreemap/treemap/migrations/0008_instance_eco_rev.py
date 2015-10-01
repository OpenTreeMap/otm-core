# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0007_auto_20150902_1534'),
    ]

    operations = [
        migrations.AddField(
            model_name='instance',
            name='eco_rev',
            field=models.IntegerField(default=1, null=True, blank=True),
        ),
    ]

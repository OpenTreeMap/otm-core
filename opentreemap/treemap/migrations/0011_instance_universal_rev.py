# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0010_eliminate_warnings_fields_w340'),
    ]

    operations = [
        migrations.AddField(
            model_name='instance',
            name='universal_rev',
            field=models.IntegerField(default=1, null=True, blank=True),
        ),
    ]

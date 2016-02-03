# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0019_merge'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='instance',
            name='bounds',
        ),
    ]

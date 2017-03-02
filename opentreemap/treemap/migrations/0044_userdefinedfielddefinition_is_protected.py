# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0043_works_management_access'),
    ]

    operations = [
        migrations.AddField(
            model_name='userdefinedfielddefinition',
            name='is_protected',
            field=models.NullBooleanField(default=False),
        ),
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0020_remove_instance_bounds'),
    ]

    operations = [
        migrations.RenameField(
            model_name='instance',
            old_name='bounds_obj',
            new_name='bounds',
        ),
    ]

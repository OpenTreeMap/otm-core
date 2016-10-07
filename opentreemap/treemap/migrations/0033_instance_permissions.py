# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0006_require_contenttypes_0002'),
        ('treemap', '0032_rename_to_role_default_permission_level'),
    ]

    operations = [
        migrations.AddField(
            model_name='role',
            name='instance_permissions',
            field=models.ManyToManyField(to='auth.Permission'),
        ),
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0004_auto_20150720_1523'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fieldpermission',
            name='permission_level',
            field=models.IntegerField(default=0, choices=[(0, 'Invisible'), (1, 'Read Only'), (2, 'Pending Write Access'), (3, 'Full Write Access')]),
        ),
        migrations.AlterField(
            model_name='role',
            name='default_permission',
            field=models.IntegerField(default=0, choices=[(0, 'Invisible'), (1, 'Read Only'), (2, 'Pending Write Access'), (3, 'Full Write Access')]),
        ),
    ]

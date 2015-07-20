# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0003_change_audit_id_to_big_int_20150708_1612'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='email',
            field=models.EmailField(unique=True, max_length=254, verbose_name='email address', blank=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='last_login',
            field=models.DateTimeField(null=True, verbose_name='last login', blank=True),
        ),
    ]

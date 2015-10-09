# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0009_restructure_replaceable_terms'),
    ]

    operations = [
        migrations.AlterField(
            model_name='instance',
            name='boundaries',
            field=models.ManyToManyField(to='treemap.Boundary'),
        ),
        migrations.AlterField(
            model_name='instance',
            name='users',
            field=models.ManyToManyField(to=settings.AUTH_USER_MODEL, through='treemap.InstanceUser'),
        ),
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='APIAccessCredential',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('access_key', models.CharField(max_length=100)),
                ('secret_key', models.CharField(max_length=256)),
                ('enabled', models.BooleanField(default=True)),
            ],
        ),
    ]

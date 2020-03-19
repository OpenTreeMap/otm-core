# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2020-03-01 04:00
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0048_merge_20200229_1923'),
    ]

    operations = [
        migrations.AddField(
            model_name='inaturalistobservation',
            name='identified_at',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='inaturalistobservation',
            name='is_identified',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='inaturalistobservation',
            name='submitted_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]

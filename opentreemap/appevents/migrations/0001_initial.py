# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import treemap.json_field


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='AppEvent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('event_type', models.CharField(max_length=255)),
                ('data', treemap.json_field.JSONField(blank=True)),
                ('triggered_at', models.DateTimeField(auto_now_add=True)),
                ('handler_assigned_at', models.DateTimeField(null=True)),
                ('handled_by', models.CharField(max_length=255, blank=True)),
                ('handled_at', models.DateTimeField(null=True)),
                ('handler_succeeded', models.NullBooleanField()),
                ('handler_log', models.TextField(blank=True)),
            ],
        ),
    ]

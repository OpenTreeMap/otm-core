# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
import treemap.json_field


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0003_change_audit_id_to_big_int_20150708_1612'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Plan',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.TextField()),
                ('description', models.TextField(blank=True)),
                ('is_published', models.BooleanField(default=False)),
                ('creation_time', models.DateTimeField(auto_now_add=True)),
                ('modified_time', models.DateTimeField(auto_now=True)),
                ('prioritization_params', treemap.json_field.JSONField()),
                ('scenarios', treemap.json_field.JSONField(null=True, blank=True)),
                ('currentScenarioId', models.IntegerField(null=True, blank=True)),
                ('instance', models.ForeignKey(to='treemap.Instance')),
                ('owner', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]

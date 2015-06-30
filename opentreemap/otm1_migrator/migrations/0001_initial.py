# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='MigrationEvent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('completed', models.DateTimeField(auto_now=True)),
                ('status', models.IntegerField(default=-1, choices=[(0, 'SUCCESS'), (1, 'FAILURE')])),
            ],
        ),
        migrations.CreateModel(
            name='OTM1CommentRelic',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('otm1_model_id', models.IntegerField()),
                ('otm2_model_id', models.IntegerField()),
                ('otm2_model_name', models.CharField(default='threadedcomment', max_length=255, editable=False)),
                ('otm1_last_child_id', models.IntegerField(null=True, blank=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='OTM1ModelRelic',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('otm1_model_id', models.IntegerField()),
                ('otm2_model_id', models.IntegerField()),
                ('otm2_model_name', models.CharField(max_length=255)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='OTM1UserRelic',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('otm1_model_id', models.IntegerField()),
                ('otm2_model_id', models.IntegerField()),
                ('otm2_model_name', models.CharField(default='user', max_length=255, editable=False)),
                ('otm1_username', models.CharField(max_length=255)),
                ('email', models.EmailField(max_length=254)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]

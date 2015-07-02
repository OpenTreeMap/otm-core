# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.core.management import call_command
from django.db import models, migrations


def load_regions(apps, schema_editor):
    call_command('loaddata', 'itree_regions.json', app_label='treemap')


def delete_regions(apps, schema_editor):
    ITreeRegion = apps.get_model('treemap', 'ITreeRegion')
    ITreeRegion.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(load_regions, delete_regions)
    ]

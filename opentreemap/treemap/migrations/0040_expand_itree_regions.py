# -*- coding: utf-8 -*-


import os

from django.conf import settings
from django.core import serializers
from django.db import migrations


def use_new_boundaries(apps, schema_editor):
    fixture_path = os.path.join(settings.PROJECT_ROOT, 'assets', 'fixtures',
                                'itree_regions_expanded.json')
    load_fixture(fixture_path, apps)


def use_old_boundaries(apps, schema_editor):
    fixture_path = os.path.join(settings.BASE_DIR, 'treemap', 'fixtures',
                                'itree_regions.json')
    load_fixture(fixture_path, apps)


# Load fixture, using this migration's model state for safety
# http://stackoverflow.com/a/32913267
def load_fixture(fixture_path, apps):
    apps_save = serializers.python.apps
    serializers.python.apps = apps
    with open(fixture_path) as fixture:
        objects = serializers.deserialize('json', fixture,
                                          ignorenonexistent=True)
        for obj in objects:
            obj.save()
    serializers.python.apps = apps_save


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0039_merge'),
    ]

    operations = [
        migrations.RunPython(use_new_boundaries, use_old_boundaries),
    ]

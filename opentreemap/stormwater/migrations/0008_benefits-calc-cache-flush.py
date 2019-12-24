# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from django.db.models import F


def bump_universal_revs(apps, schema_editor):
    Instance = apps.get_model("treemap", "Instance")
    attr = "universal_rev"
    Instance.objects.all().update(universal_rev=F(attr) + 1)


class Migration(migrations.Migration):

    dependencies = [
        ("stormwater", "0007_drainage_area_permissions"),
        ("treemap", "0029_merge"),
    ]

    operations = [migrations.RunPython(bump_universal_revs, migrations.RunPython.noop)]

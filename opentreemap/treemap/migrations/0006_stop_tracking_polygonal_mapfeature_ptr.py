# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def delete_polygonal_map_feature_references(apps, schema_editor):
    # Like MapFeature, PolygonalMapFeature subclasses contain a pointer to the
    # parent table.  Unlike MapFeature, we forgot to exclude this field from
    # the audit and field permission system.  We now no longer track it, and
    # this migration removes any references that already exist
    FieldPermission = apps.get_model('treemap', 'FieldPermission')
    Audit = apps.get_model('treemap', 'Audit')

    FieldPermission.objects \
        .filter(field_name='polygonalmapfeature_ptr').delete()
    Audit.objects.filter(field='polygonalmapfeature_ptr').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0005_auto_20150729_1046'),
    ]

    operations = [
        migrations.RunPython(delete_polygonal_map_feature_references,
                             migrations.RunPython.noop)
    ]

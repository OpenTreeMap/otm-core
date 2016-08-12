# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from django.db.models import F


def add_permissions_all(apps, schema_editor):
    Instance = apps.get_model('treemap', 'Instance')
    Role = apps.get_model('treemap', 'Role')
    FieldPermission = apps.get_model('treemap', 'FieldPermission')

    # Adapted from treemap.audit.add_default_permissions.
    # We can't use that function directly, partly because of its
    # dependencies on model classes, which aren't the right version
    # for a migration, and partly because a migration is a snapshot
    # in time, and we need to snapshot the logic as well.
    def update_field_permissions(perm_specs, role, instance):
        existing = FieldPermission.objects.filter(
            role=role, instance=instance)
        if existing.exists():
            for perm in perm_specs:
                perm['defaults'] = {
                    'permission_level': role.default_permission}
                FieldPermission.objects.get_or_create(**perm)
            return False
        else:
            perm_specs = [FieldPermission(**perm) for perm in perm_specs]
            for perm in perm_specs:
                perm.permission_level = role.default_permission
            FieldPermission.objects.bulk_create(perm_specs)
            return True

    for instance in Instance.objects.filter(config__contains='"Plot",'):
        types = instance.map_feature_types
        if 'Bioswale' in types or 'RainGarden' in types:
            for role in Role.objects.filter(instance=instance):
                perm_specs = [
                    {'model_name': 'Bioswale',
                     'field_name': 'drainage_area',
                     'role': role,
                     'instance': instance},
                    {'model_name': 'RainGarden',
                     'field_name': 'drainage_area',
                     'role': role,
                     'instance': instance}]
                update_field_permissions(perm_specs, role, instance)

    # Adapted from treemap.object_caches.increment_adjuncts_timestamp.
    # That function has a dependency on treemap.instance.Instance,
    # which wouldn't be the right version mid-migration.
    # We need to update the adjuncts_timestamp in the database to cause the
    # server, executing in another process, to update itself.
    # Note that this is only important for developers, who don't regularly do
    # vagrant destroy, because on the AWS machines, the migration will
    # inevitably be accompanied by a fresh deployment, which won't have
    # anything cached.
    Instance.objects.all() \
        .update(adjuncts_timestamp=F('adjuncts_timestamp') + 1)


def remove_drainage_area_permissions(apps, schema_editor):
    FieldPermission = apps.get_model('treemap', 'FieldPermission')
    for perm in FieldPermission.objects.filter(field_name='drainage_area'):
        perm.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('stormwater', '0006_stormwater_drainage_area'),
        ('treemap', '0029_merge'),
    ]

    operations = [
        migrations.RunPython(add_permissions_all,
                             remove_drainage_area_permissions)
    ]

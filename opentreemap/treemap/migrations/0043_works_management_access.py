# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


# Note: to reuse this data migration when adding a new permission
# in the future, copy the code and update these two lines:

_new_permission_codename = 'access_works_management'
_default_role_names = ['administrator']


def add_permission(apps, schema_editor):
    Permission, Instance, instance_content_type, Role = _get_models(apps)

    # Create new permission
    perm = Permission.objects.create(
        codename=_new_permission_codename,
        name=_new_permission_codename,
        content_type=instance_content_type
    )

    # Add new permission to specified roles in all instances
    for instance in Instance.objects.all():
        for role in Role.objects.filter(instance=instance):
            if role.name in _default_role_names:
                role.instance_permissions.add(perm)


def remove_permission(apps, schema_editor):
    Permission, Instance, instance_content_type, Role = _get_models(apps)

    perm = Permission.objects.get(codename=_new_permission_codename,
                                  content_type=instance_content_type)

    # Remove permission from all roles
    ThroughModel = Role.instance_permissions.through
    ThroughModel.objects.filter(permission_id=perm.id).delete()

    # Remove permission itself
    Permission.objects.filter(id=perm.id).delete()


def _get_models(apps):
    Instance = apps.get_model('treemap', 'Instance')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    instance_content_type = ContentType.objects.get_for_model(Instance)
    Role = apps.get_model('treemap', 'Role')
    Permission = apps.get_model('auth', 'Permission')
    return Permission, Instance, instance_content_type, Role


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0042_auto_20170112_1603'),
    ]

    operations = [
        migrations.RunPython(add_permission, remove_permission),
    ]

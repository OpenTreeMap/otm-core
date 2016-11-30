# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def change_labels(apps, term):
    Permission = apps.get_model('auth', 'Permission')
    add_plot = Permission.objects.filter(codename='add_plot')
    delete_plot = Permission.objects.filter(codename='delete_plot')
    add_plot.update(name='Can add {}'.format(term))
    delete_plot.update(name='Can delete {}'.format(term))


def fix_labels(apps, schema_editor):
    change_labels(apps, 'planting site')


def revert_labels(apps, schema_editor):
    change_labels(apps, 'plot')


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0036_assign_role_add_delete_permissions'),
    ]

    operations = [
        migrations.RunPython(fix_labels, revert_labels),
    ]

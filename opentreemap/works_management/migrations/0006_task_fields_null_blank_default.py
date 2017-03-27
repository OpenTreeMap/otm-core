# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('works_management', '0005_blank_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='closed_on',
            field=models.DateField(default=None, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='task',
            name='field_notes',
            field=models.TextField(default='', blank=True),
        ),
        migrations.AlterField(
            model_name='task',
            name='office_notes',
            field=models.TextField(default='', blank=True),
        ),
        migrations.AlterField(
            model_name='task',
            name='scheduled_on',
            field=models.DateField(default=None, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='task',
            name='status',
            field=models.IntegerField(default=0, blank=True, choices=[(0, 'Requested'), (1, 'Scheduled'), (2, 'Completed'), (3, 'Canceled')]),
        ),
        migrations.AlterField(
            model_name='task',
            name='work_order',
            field=models.ForeignKey(default=None, to='works_management.WorkOrder'),
        ),
    ]

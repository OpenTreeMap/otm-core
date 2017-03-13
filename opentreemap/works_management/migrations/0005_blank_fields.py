# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('works_management', '0004_reference_number_unique'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='field_notes',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='task',
            name='office_notes',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='task',
            name='team',
            field=models.ForeignKey(blank=True, to='works_management.Team', null=True),
        ),
        migrations.AlterField(
            model_name='task',
            name='work_order',
            field=models.ForeignKey(blank=True, to='works_management.WorkOrder', null=True),
        ),
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('works_management', '0003_reference_number_default'),
    ]

    operations = [
        migrations.AlterField(
            model_name='task',
            name='reference_number',
            field=models.IntegerField(),
        ),
        migrations.AlterField(
            model_name='workorder',
            name='reference_number',
            field=models.IntegerField(),
        ),
        migrations.AlterUniqueTogether(
            name='task',
            unique_together=set([('instance', 'reference_number')]),
        ),
        migrations.AlterUniqueTogether(
            name='workorder',
            unique_together=set([('instance', 'reference_number')]),
        ),
    ]

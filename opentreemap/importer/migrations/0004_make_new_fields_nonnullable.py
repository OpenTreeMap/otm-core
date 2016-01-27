# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('importer', '0003_add_lost_job_bookkeeping_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='speciesimportevent',
            name='is_lost',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='treeimportevent',
            name='is_lost',
            field=models.BooleanField(default=False),
        ),
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('importer', '0002_auto_20150630_1556'),
    ]

    operations = [
        migrations.AlterField(
            model_name='speciesimportrow',
            name='idx',
            field=models.IntegerField(db_index=True),
        ),
        migrations.AlterField(
            model_name='treeimportrow',
            name='idx',
            field=models.IntegerField(db_index=True),
        ),
    ]

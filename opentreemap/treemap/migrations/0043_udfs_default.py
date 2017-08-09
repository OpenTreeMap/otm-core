# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
import treemap.udf


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0042_auto_20170112_1603'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mapfeature',
            name='udfs',
            field=treemap.udf.UDFField(default=lambda: {},
                                       db_index=True, blank=True),
        ),
        migrations.AlterField(
            model_name='species',
            name='udfs',
            field=treemap.udf.UDFField(default=lambda: {},
                                       db_index=True, blank=True),
        ),
        migrations.AlterField(
            model_name='tree',
            name='udfs',
            field=treemap.udf.UDFField(default=lambda: {},
                                       db_index=True, blank=True),
        ),
    ]

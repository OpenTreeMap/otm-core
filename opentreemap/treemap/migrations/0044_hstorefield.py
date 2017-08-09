# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
import treemap.udf


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0043_species_not_udf_model'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mapfeature',
            name='udfs',
            field=treemap.udf.UDFPostgresField(
                default=treemap.udf.UDFDictionary,
                db_index=True, db_column='udfs', blank=True),
        ),
        migrations.AlterField(
            model_name='tree',
            name='udfs',
            field=treemap.udf.UDFPostgresField(
                default=treemap.udf.UDFDictionary,
                db_index=True, db_column='udfs', blank=True),
        ),
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0024_add_species_verbose_names'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mapfeature',
            name='address_city',
            field=models.CharField(default='', max_length=255, verbose_name='City', blank=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='mapfeature',
            name='address_street',
            field=models.CharField(default='', max_length=255, verbose_name='Address', blank=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='mapfeature',
            name='address_zip',
            field=models.CharField(default='', max_length=30, verbose_name='Postal Code', blank=True),
            preserve_default=False,
        ),
    ]

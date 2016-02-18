# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0017_copy_bounds_to_separate_model'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='species',
            options={'verbose_name': 'Species', 'verbose_name_plural': 'Species'},
        ),
        migrations.AlterField(
            model_name='species',
            name='is_native',
            field=models.NullBooleanField(verbose_name='Native to Region'),
        ),
        migrations.AlterField(
            model_name='species',
            name='palatable_human',
            field=models.NullBooleanField(verbose_name='Edible'),
        ),
    ]

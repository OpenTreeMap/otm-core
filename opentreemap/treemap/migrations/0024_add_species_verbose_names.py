# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0023_merge'),
    ]

    operations = [
        migrations.AlterField(
            model_name='species',
            name='common_name',
            field=models.CharField(max_length=255, verbose_name='Common Name'),
        ),
        migrations.AlterField(
            model_name='species',
            name='cultivar',
            field=models.CharField(max_length=255, verbose_name='Cultivar', blank=True),
        ),
        migrations.AlterField(
            model_name='species',
            name='fact_sheet_url',
            field=models.URLField(max_length=255, verbose_name='Fact Sheet URL', blank=True),
        ),
        migrations.AlterField(
            model_name='species',
            name='fall_conspicuous',
            field=models.NullBooleanField(verbose_name='Fall Conspicuous'),
        ),
        migrations.AlterField(
            model_name='species',
            name='flower_conspicuous',
            field=models.NullBooleanField(verbose_name='Flower Conspicuous'),
        ),
        migrations.AlterField(
            model_name='species',
            name='flowering_period',
            field=models.CharField(max_length=255, verbose_name='Flowering Period', blank=True),
        ),
        migrations.AlterField(
            model_name='species',
            name='fruit_or_nut_period',
            field=models.CharField(max_length=255, verbose_name='Fruit or Nut Period', blank=True),
        ),
        migrations.AlterField(
            model_name='species',
            name='genus',
            field=models.CharField(max_length=255, verbose_name='Genus'),
        ),
        migrations.AlterField(
            model_name='species',
            name='has_wildlife_value',
            field=models.NullBooleanField(verbose_name='Has Wildlife Value'),
        ),
        migrations.AlterField(
            model_name='species',
            name='max_diameter',
            field=models.IntegerField(default=200, verbose_name='Max Diameter'),
        ),
        migrations.AlterField(
            model_name='species',
            name='max_height',
            field=models.IntegerField(default=800, verbose_name='Max Height'),
        ),
        migrations.AlterField(
            model_name='species',
            name='other_part_of_name',
            field=models.CharField(max_length=255, verbose_name='Other Part of Name', blank=True),
        ),
        migrations.AlterField(
            model_name='species',
            name='plant_guide_url',
            field=models.URLField(max_length=255, verbose_name='Plant Guide URL', blank=True),
        ),
        migrations.AlterField(
            model_name='species',
            name='species',
            field=models.CharField(max_length=255, verbose_name='Species', blank=True),
        ),
    ]

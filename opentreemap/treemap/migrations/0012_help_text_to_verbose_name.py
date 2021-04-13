# -*- coding: utf-8 -*-


from django.db import models, migrations
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0011_instance_universal_rev'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mapfeature',
            name='address_city',
            field=models.CharField(max_length=255, null=True, verbose_name='City', blank=True),
        ),
        migrations.AlterField(
            model_name='mapfeature',
            name='address_street',
            field=models.CharField(max_length=255, null=True, verbose_name='Address', blank=True),
        ),
        migrations.AlterField(
            model_name='mapfeature',
            name='address_zip',
            field=models.CharField(max_length=30, null=True, verbose_name='Postal Code', blank=True),
        ),
        migrations.AlterField(
            model_name='mapfeature',
            name='updated_at',
            field=models.DateTimeField(default=django.utils.timezone.now, verbose_name='Last Updated'),
        ),
        migrations.AlterField(
            model_name='plot',
            name='length',
            field=models.FloatField(null=True, verbose_name='Planting Site Length', blank=True),
        ),
        migrations.AlterField(
            model_name='plot',
            name='width',
            field=models.FloatField(null=True, verbose_name='Planting Site Width', blank=True),
        ),
        migrations.AlterField(
            model_name='tree',
            name='canopy_height',
            field=models.FloatField(null=True, verbose_name='Canopy Height', blank=True),
        ),
        migrations.AlterField(
            model_name='tree',
            name='date_planted',
            field=models.DateField(null=True, verbose_name='Date Planted', blank=True),
        ),
        migrations.AlterField(
            model_name='tree',
            name='date_removed',
            field=models.DateField(null=True, verbose_name='Date Removed', blank=True),
        ),
        migrations.AlterField(
            model_name='tree',
            name='diameter',
            field=models.FloatField(null=True, verbose_name='Tree Diameter', blank=True),
        ),
        migrations.AlterField(
            model_name='tree',
            name='height',
            field=models.FloatField(null=True, verbose_name='Tree Height', blank=True),
        ),
        migrations.AlterField(
            model_name='tree',
            name='species',
            field=models.ForeignKey(on_delete=models.CASCADE, verbose_name='Species', blank=True, to='treemap.Species', null=True),
        ),
    ]

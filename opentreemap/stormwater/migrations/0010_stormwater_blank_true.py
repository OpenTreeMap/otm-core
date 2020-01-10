# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stormwater', '0009_drainage_area_imperial_units'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bioswale',
            name='drainage_area',
            field=models.FloatField(blank=True, null=True, verbose_name='Adjacent Drainage Area', error_messages={'invalid': 'Please enter a number.'}),
        ),
        migrations.AlterField(
            model_name='raingarden',
            name='drainage_area',
            field=models.FloatField(blank=True, null=True, verbose_name='Adjacent Drainage Area', error_messages={'invalid': 'Please enter a number.'}),
        ),
    ]

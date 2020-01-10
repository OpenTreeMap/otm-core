# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stormwater', '0005_help_text_to_verbose_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='bioswale',
            name='drainage_area',
            field=models.FloatField(null=True, verbose_name='Adjacent Drainage Area', error_messages={'invalid': 'Please enter a number.'}),
        ),
        migrations.AddField(
            model_name='raingarden',
            name='drainage_area',
            field=models.FloatField(null=True, verbose_name='Adjacent Drainage Area', error_messages={'invalid': 'Please enter a number.'}),
        ),
    ]

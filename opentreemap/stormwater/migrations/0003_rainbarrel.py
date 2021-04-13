# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0007_auto_20150902_1534'),
        ('stormwater', '0002_raingarden'),
    ]

    operations = [
        migrations.CreateModel(
            name='RainBarrel',
            fields=[
                ('mapfeature_ptr', models.OneToOneField(on_delete=models.CASCADE, parent_link=True, auto_created=True, primary_key=True, serialize=False, to='treemap.MapFeature')),
                ('capacity', models.FloatField(help_text='Capacity')),
            ],
            options={
                'abstract': False,
            },
            bases=('treemap.mapfeature',),
        ),
    ]

# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stormwater', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RainGarden',
            fields=[
                ('polygonalmapfeature_ptr', models.OneToOneField(on_delete=models.CASCADE, parent_link=True, auto_created=True, primary_key=True, serialize=False, to='stormwater.PolygonalMapFeature')),
            ],
            options={
                'abstract': False,
            },
            bases=('stormwater.polygonalmapfeature',),
        ),
    ]

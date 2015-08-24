# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stormwater', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RainGarden',
            fields=[
                ('polygonalmapfeature_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='stormwater.PolygonalMapFeature')),
            ],
            options={
                'abstract': False,
            },
            bases=('stormwater.polygonalmapfeature',),
        ),
    ]

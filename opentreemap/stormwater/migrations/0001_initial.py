# -*- coding: utf-8 -*-


from django.db import models, migrations
import django.contrib.gis.db.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PolygonalMapFeature',
            fields=[
                ('mapfeature_ptr', models.OneToOneField(on_delete=models.CASCADE, parent_link=True, auto_created=True, primary_key=True, serialize=False, to='treemap.MapFeature')),
                ('polygon', django.contrib.gis.db.models.fields.MultiPolygonField(srid=3857)),
            ],
            options={
                'abstract': False,
            },
            bases=('treemap.mapfeature',),
        ),
        migrations.CreateModel(
            name='Bioswale',
            fields=[
                ('polygonalmapfeature_ptr', models.OneToOneField(on_delete=models.CASCADE, parent_link=True, auto_created=True, primary_key=True, serialize=False, to='stormwater.PolygonalMapFeature')),
            ],
            options={
                'abstract': False,
            },
            bases=('stormwater.polygonalmapfeature',),
        ),
    ]

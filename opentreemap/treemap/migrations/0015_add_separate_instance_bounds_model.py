# -*- coding: utf-8 -*-


from django.db import migrations, models
import django.contrib.gis.db.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0014_change_empty_multichoice_values'),
    ]

    operations = [
        migrations.CreateModel(
            name='InstanceBounds',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('geom', django.contrib.gis.db.models.fields.MultiPolygonField(srid=3857)),
            ],
        ),
        migrations.AddField(
            model_name='instance',
            name='bounds_obj',
            field=models.OneToOneField(on_delete=models.CASCADE, null=True, blank=True, to='treemap.InstanceBounds'),
        ),
    ]

# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='SpeciesImportEvent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('file_name', models.CharField(max_length=255)),
                ('errors', models.TextField(default='')),
                ('field_order', models.TextField(default='')),
                ('created', models.DateTimeField(auto_now=True)),
                ('completed', models.DateTimeField(null=True, blank=True)),
                ('status', models.IntegerField(default=1)),
                ('task_id', models.CharField(default='', max_length=50, blank=True)),
                ('max_diameter_conversion_factor', models.FloatField(default=1.0)),
                ('max_tree_height_conversion_factor', models.FloatField(default=1.0)),
            ],
        ),
        migrations.CreateModel(
            name='SpeciesImportRow',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('data', models.TextField()),
                ('idx', models.IntegerField()),
                ('finished', models.BooleanField(default=False)),
                ('errors', models.TextField(default='')),
                ('status', models.IntegerField(default=3)),
                ('merged', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='TreeImportEvent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('file_name', models.CharField(max_length=255)),
                ('errors', models.TextField(default='')),
                ('field_order', models.TextField(default='')),
                ('created', models.DateTimeField(auto_now=True)),
                ('completed', models.DateTimeField(null=True, blank=True)),
                ('status', models.IntegerField(default=1)),
                ('task_id', models.CharField(default='', max_length=50, blank=True)),
                ('plot_length_conversion_factor', models.FloatField(default=1.0)),
                ('plot_width_conversion_factor', models.FloatField(default=1.0)),
                ('diameter_conversion_factor', models.FloatField(default=1.0)),
                ('tree_height_conversion_factor', models.FloatField(default=1.0)),
                ('canopy_height_conversion_factor', models.FloatField(default=1.0)),
            ],
        ),
        migrations.CreateModel(
            name='TreeImportRow',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('data', models.TextField()),
                ('idx', models.IntegerField()),
                ('finished', models.BooleanField(default=False)),
                ('errors', models.TextField(default='')),
                ('status', models.IntegerField(default=3)),
                ('import_event', models.ForeignKey(on_delete=models.CASCADE, to='importer.TreeImportEvent')),
            ],
        ),
    ]

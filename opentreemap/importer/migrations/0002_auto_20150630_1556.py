# -*- coding: utf-8 -*-


from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('importer', '0001_initial'),
        ('treemap', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='treeimportrow',
            name='plot',
            field=models.ForeignKey(on_delete=models.CASCADE, blank=True, to='treemap.Plot', null=True),
        ),
        migrations.AddField(
            model_name='treeimportevent',
            name='instance',
            field=models.ForeignKey(on_delete=models.CASCADE, to='treemap.Instance'),
        ),
        migrations.AddField(
            model_name='treeimportevent',
            name='owner',
            field=models.ForeignKey(on_delete=models.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='speciesimportrow',
            name='import_event',
            field=models.ForeignKey(on_delete=models.CASCADE, to='importer.SpeciesImportEvent'),
        ),
        migrations.AddField(
            model_name='speciesimportrow',
            name='species',
            field=models.ForeignKey(on_delete=models.CASCADE, blank=True, to='treemap.Species', null=True),
        ),
        migrations.AddField(
            model_name='speciesimportevent',
            name='instance',
            field=models.ForeignKey(on_delete=models.CASCADE, to='treemap.Instance'),
        ),
        migrations.AddField(
            model_name='speciesimportevent',
            name='owner',
            field=models.ForeignKey(on_delete=models.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
    ]

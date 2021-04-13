# -*- coding: utf-8 -*-


from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0003_change_audit_id_to_big_int_20150708_1612'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ExportJob',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('status', models.IntegerField(default=0, choices=[(0, 'Pending'), (1, 'Query returned no trees or planting sites.'), (2, 'User has no permissions on this model'), (3, 'Ready'), (-1, 'Something went wrong with your export.')])),
                ('outfile', models.FileField(upload_to='exports/%Y/%m/%d')),
                ('created', models.DateTimeField(null=True, blank=True)),
                ('modified', models.DateTimeField(null=True, blank=True)),
                ('description', models.CharField(max_length=255)),
                ('instance', models.ForeignKey(on_delete=models.CASCADE, to='treemap.Instance')),
                ('user', models.ForeignKey(on_delete=models.CASCADE, blank=True, to=settings.AUTH_USER_MODEL, null=True)),
            ],
        ),
    ]

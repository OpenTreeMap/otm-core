# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import treemap.audit
from django.conf import settings
import treemap.udf


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('treemap', '0043_works_management_access'),
    ]

    operations = [
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('udfs', treemap.udf.UDFField(db_index=True, blank=True)),
                ('office_notes', models.TextField()),
                ('field_notes', models.TextField()),
                ('status', models.IntegerField(default=0, choices=[(0, 'Requested'), (1, 'Scheduled'), (2, 'Completed'), (3, 'Canceled')])),
                ('requested_on', models.DateField()),
                ('scheduled_on', models.DateField()),
                ('closed_on', models.DateField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
                ('instance', models.ForeignKey(to='treemap.Instance')),
                ('map_feature', models.ForeignKey(to='treemap.MapFeature')),
            ],
            options={
                'abstract': False,
            },
            bases=(treemap.audit.Auditable, treemap.audit.UserTrackable, models.Model),
        ),
        migrations.CreateModel(
            name='Team',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('instance', models.ForeignKey(to='treemap.Instance')),
            ],
        ),
        migrations.CreateModel(
            name='WorkOrder',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
                ('instance', models.ForeignKey(to='treemap.Instance')),
            ],
            bases=(models.Model, treemap.audit.Auditable),
        ),
        migrations.AddField(
            model_name='task',
            name='team',
            field=models.ForeignKey(to='works_management.Team', null=True),
        ),
        migrations.AddField(
            model_name='task',
            name='work_order',
            field=models.ForeignKey(related_name='tasks', to='works_management.WorkOrder', null=True),
        ),
    ]

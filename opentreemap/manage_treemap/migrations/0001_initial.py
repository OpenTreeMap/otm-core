# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('treemap', '0042_auto_20170112_1603'),
    ]

    operations = [
        migrations.CreateModel(
            name='InstanceInvitation',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('email', models.CharField(max_length=255, validators=[django.core.validators.EmailValidator()])),
                ('admin', models.BooleanField(default=False)),
                ('created', models.DateField(auto_now_add=True)),
                ('updated', models.DateField(auto_now=True)),
                ('accepted', models.BooleanField(default=False)),
                ('activation_key', models.CharField(unique=True, max_length=40)),
                ('created_by', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
                ('instance', models.ForeignKey(to='treemap.Instance')),
                ('role', models.ForeignKey(to='treemap.Role')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='instanceinvitation',
            unique_together=set([('email', 'instance')]),
        ),
    ]

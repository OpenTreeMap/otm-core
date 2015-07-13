# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('otm_comments', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='enhancedthreadedcommentflag',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='enhancedthreadedcomment',
            name='instance',
            field=models.ForeignKey(to='treemap.Instance'),
        ),
    ]

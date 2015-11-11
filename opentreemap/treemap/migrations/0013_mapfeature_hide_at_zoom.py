# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0012_help_text_to_verbose_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='mapfeature',
            name='hide_at_zoom',
            field=models.IntegerField(default=None, null=True, db_index=True, blank=True),
        ),
    ]

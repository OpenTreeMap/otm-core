# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0006_stop_tracking_polygonal_mapfeature_ptr'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='userdefinedfielddefinition',
            unique_together=set([('instance', 'model_type', 'name')]),
        ),
    ]

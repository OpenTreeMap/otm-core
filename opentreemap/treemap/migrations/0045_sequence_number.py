# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0044_userdefinedfielddefinition_is_protected'),
    ]

    operations = [
        migrations.AddField(
            model_name='instance',
            name='task_sequence_number',
            field=models.IntegerField(default=1, null=True),
        ),
        migrations.AddField(
            model_name='instance',
            name='work_order_sequence_number',
            field=models.IntegerField(default=1, null=True),
        ),
    ]

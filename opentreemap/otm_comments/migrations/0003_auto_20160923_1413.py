# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("otm_comments", "0002_auto_20150630_1556"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="enhancedthreadedcomment",
            options={
                "ordering": ("submit_date",),
                "verbose_name": "comment",
                "verbose_name_plural": "comments",
                "permissions": [("can_moderate", "Can moderate comments")],
            },
        ),
    ]

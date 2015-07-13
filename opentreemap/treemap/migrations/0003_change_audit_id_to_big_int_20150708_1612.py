# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0002_add_itree_regions_20150701_1809'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE treemap_audit ALTER COLUMN id TYPE bigint",
            reverse_sql="ALTER TABLE treemap_audit ALTER COLUMN id TYPE int"),
        migrations.RunSQL(
            sql="ALTER TABLE treemap_audit ALTER COLUMN ref_id TYPE bigint",
            reverse_sql="ALTER TABLE treemap_audit ALTER COLUMN ref_id TYPE int"),
    ]

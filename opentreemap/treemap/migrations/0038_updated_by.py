# -*- coding: utf-8 -*-


from django.db import migrations, models
from django.conf import settings


# This migration adds the `updated_by_id` column to the
# `treemap_mapfeature` table.
# As a new column, it is nullable.
#
# Before you can run the later migration to remove nullable, run
# `manage.py set_mapfeature_updated_by` to populate the column.
class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0037_fix_plot_add_delete_permission_labels'),
    ]

    operations = [
        migrations.AddField(
            model_name='mapfeature',
            name='updated_by',
            field=models.ForeignKey(on_delete=models.CASCADE, blank=True, null=True,
                                    to=settings.AUTH_USER_MODEL),
        ),
    ]

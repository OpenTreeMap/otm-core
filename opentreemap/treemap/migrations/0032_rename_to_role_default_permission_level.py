# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0031_add_custom_id_to_default_search_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='role',
            name='default_permission',
            field=models.IntegerField(default=0, db_column='default_permission', choices=[(0, 'Invisible'), (1, 'Read Only'), (2, 'Pending Write Access'), (3, 'Full Write Access')]),
        ),
        migrations.RenameField(
            model_name='role',
            old_name='default_permission',
            new_name='default_permission_level',
        ),
    ]

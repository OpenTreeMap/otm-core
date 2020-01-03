# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0029_merge'),
    ]

    operations = [
        migrations.AlterField(
            model_name='plot',
            name='owner_orig_id',
            field=models.CharField(max_length=255, null=True, verbose_name='Custom ID', blank=True),
        ),
    ]

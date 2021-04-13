# -*- coding: utf-8 -*-


from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0041_search_by_user'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mapfeature',
            name='updated_by',
            field=models.ForeignKey(on_delete=models.CASCADE, verbose_name='Last Updated By', blank=True, to=settings.AUTH_USER_MODEL, null=True),
        ),
    ]

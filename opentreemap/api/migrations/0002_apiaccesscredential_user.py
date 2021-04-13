# -*- coding: utf-8 -*-


from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='apiaccesscredential',
            name='user',
            field=models.ForeignKey(on_delete=models.CASCADE, to=settings.AUTH_USER_MODEL, null=True),
        ),
    ]

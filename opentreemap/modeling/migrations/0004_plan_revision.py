# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('modeling', '0003_plan_zoom_lat_lng'),
    ]

    operations = [
        migrations.AddField(
            model_name='plan',
            name='revision',
            field=models.IntegerField(default=0),
        ),
    ]

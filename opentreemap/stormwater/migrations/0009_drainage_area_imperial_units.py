# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from django.db.models import F


SQ_M_TO_SQ_FT = 10.7639
SQ_FT_TO_SQ_M = 1 / SQ_M_TO_SQ_FT


def convert_units_all(to_imperial, apps, schema_editor):
    conversion_factor = SQ_M_TO_SQ_FT if to_imperial else SQ_FT_TO_SQ_M
    RainGarden = apps.get_model('stormwater', 'RainGarden')
    Bioswale = apps.get_model('stormwater', 'Bioswale')
    RainGarden.objects.all() \
        .update(drainage_area=F('drainage_area') * conversion_factor)
    Bioswale.objects.all() \
        .update(drainage_area=F('drainage_area') * conversion_factor)


class Migration(migrations.Migration):

    dependencies = [
        ('stormwater', '0008_benefits-calc-cache-flush'),
        ('treemap', '0029_merge'),
    ]

    operations = [
        migrations.RunPython(
            lambda apps, ed: convert_units_all(True, apps, ed),
            lambda apps, ed: convert_units_all(False, apps, ed))
    ]

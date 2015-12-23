# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from treemap.udf import UDFDictionary


def set_empty_multichoice_values_to_none(apps, schema_editor):
    UserDefinedFieldDefinition = apps.get_model(
        'treemap', 'UserDefinedFieldDefinition')
    udfds = (UserDefinedFieldDefinition.objects
             .filter(datatype__contains='multichoice'))
    print()
    for udfd in udfds:
        type = udfd.model_type
        if type in ('Bioswale', 'RainGarden', 'RainBarrel'):
            Model = apps.get_model('stormwater', type)
        else:
            Model = apps.get_model('treemap', type)
        objs = (Model.objects
                .filter(instance=udfd.instance)
                .filter(udfs__contains={udfd.name: '[]'})
                )
        for obj in objs:
            # Note: this is doing
            #     obj.udfs[udfd.name] = None
            # in a migration-safe way
            super(UDFDictionary, obj.udfs).__setitem__(udfd.name, None)
            obj.save_base()
        if len(objs) > 0:
            print('Updated %s empty multichoice values for %s udf "%s" (%s)'
                  % (len(objs), udfd.model_type, udfd.name,
                     udfd.instance.url_name))


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0013_mapfeature_hide_at_zoom'),
    ]

    # Note: reverse migration unnecessary since NULL is already a valid value
    # for a multichoice field
    operations = [
        migrations.RunPython(set_empty_multichoice_values_to_none,
                             migrations.RunPython.noop)
    ]

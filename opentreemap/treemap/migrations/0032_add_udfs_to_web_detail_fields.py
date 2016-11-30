# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from copy import deepcopy

from django.db import migrations, models

from treemap.util import to_object_name
from treemap.search_fields import DEFAULT_WEB_DETAIL_FIELDS


def add_udfs_to_web_detail_fields(apps, schema_editor):
    Instance = apps.get_model("treemap", "Instance")
    UserDefinedFieldDefinition = apps.get_model("treemap", "UserDefinedFieldDefinition")

    for instance in Instance.objects.all():
        scalar_udfs = UserDefinedFieldDefinition.objects \
            .filter(iscollection=False, instance=instance) \
            .order_by('name')

        # Nothing to add to the configs
        if not scalar_udfs:
            continue

        if 'web_detail_fields' not in instance.config:
            instance.config['web_detail_fields'] = deepcopy(DEFAULT_WEB_DETAIL_FIELDS)

        for udf in scalar_udfs:
            for group in instance.config['web_detail_fields']:
                if 'model' in group and group['model'] == to_object_name(udf.model_type):
                    field_keys = group.get('field_keys')

                    udf_full_name = to_object_name(udf.model_type) + '.udf:' + udf.name
                    if 'field_keys' in group and udf_full_name not in field_keys:
                        field_keys.append(udf_full_name)

        instance.save()


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0031_add_custom_id_to_default_search_fields'),
    ]

    operations = [
        migrations.RunPython(add_udfs_to_web_detail_fields,
                             migrations.RunPython.noop),
    ]

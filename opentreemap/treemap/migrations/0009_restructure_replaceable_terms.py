# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def replace_terms_forward(apps, schema_editor):
    Instance = apps.get_model("treemap", "Instance")
    instances = Instance.objects.filter(config__contains='\"terms\":')
    for instance in instances:
        terms = instance.config.terms
        if (('Resource' and 'Resources' in terms
             and not isinstance(terms['Resource'], dict))):
            new_dict = {'singular': terms['Resource'],
                        'plural': terms['Resources']}
            del terms['Resources']
            terms['Resource'] = new_dict
            instance.save()


def replace_terms_backward(apps, schema_editor):
    Instance = apps.get_model("treemap", "Instance")
    instances = Instance.objects.filter(config__contains='\"terms\":')
    for instance in instances:
        terms = instance.config.terms
        if (('Resource' in terms
             and isinstance(terms['Resource'], dict))):
            terms['Resources'] = terms['Resource.plural']
            terms['Resource'] = terms['Resource.singular']
            instance.save()


class Migration(migrations.Migration):

    dependencies = [
        ('treemap', '0008_instance_eco_rev'),
    ]

    operations = [
        migrations.RunPython(replace_terms_forward, replace_terms_backward),
    ]

# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf import settings
from django.contrib.contenttypes.models import ContentType

from treemap.models import Species, Instance, Tree, Plot, Audit, TreePhoto
from treemap.management.util import InstanceDataCommand

from otm1_migrator.models import OTM1ModelRelic


class Command(InstanceDataCommand):
    def pseudo_assert_equals(self, item1, item2, description):
        isEqual = 'SUCCESS' if item1 == item2 else 'WARNING'
        self.stdout.write('testing assertion: %s ... %s - %s / %s'
                          % (description, isEqual, item1, item2))

    def test_class(self, clz, instance_id=None):
        name = clz.__name__.lower()
        objects = clz.objects.all()

        if instance_id:
            objects = objects.filter(instance_id=instance_id)

        object_count = objects.count()
        object_relics = OTM1ModelRelic.objects.filter(
            otm2_model_name__iexact=name)

        if instance_id:
            object_relics = object_relics.filter(instance_id=instance_id)

        object_relic_count = object_relics.count()

        self.pseudo_assert_equals(object_count, object_relic_count,
                                  'there are an equal number of '
                                  '%s and %s relics.'
                                  % (name, name))

    def handle(self, *args, **options):

        if settings.DEBUG:
            self.stdout.write('In order to run this command you must manually'
                              'set DEBUG=False in your settings file. '
                              'Unfortunately, django runs out of memory when '
                              'this command is run in DEBUG mode.')
            return 1

        try:
            instance_id = options['instance']
            Instance.objects.get(pk=instance_id)
        except Instance.DoesNotExist:
            self.stdout.write('Invalid instance provided.')
            return 1

        for clz in (Tree, Plot, Audit, TreePhoto, Species):
            self.test_class(clz, instance_id=instance_id)

        self.test_class(ContentType)

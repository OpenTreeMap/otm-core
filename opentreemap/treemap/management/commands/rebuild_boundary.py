# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import logging
from optparse import make_option

from django.core.management.base import BaseCommand

from treemap.instance import Instance
from treemap.models import Boundary

logger = logging.getLogger('')


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--instance',
                    dest='instance',
                    help='The instance to rebuild'),
    )

    def handle(self, *args, **options):
        instance_id = options['instance']
        if not instance_id:
            print('You must specify an instance')
            return

        instance = Instance.objects.get(pk=instance_id)

        instance.boundaries = Boundary.objects.filter(
            geom__intersects=instance.bounds)

        instance.geo_rev += 1
        instance.save()

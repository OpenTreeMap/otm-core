# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import logging
import time

from django.core.management.base import BaseCommand
from django.db import transaction

from treemap.instance import Instance
from opentreemap.integrations import inaturalist
from django.db import IntegrityError, connection, transaction

from django.conf import settings

logger = logging.getLogger('')

class Command(BaseCommand):
    """
    Migrate all images from the file
    """

    def add_arguments(self, parser):
        parser.add_argument(
            'instance_name',
            help='Specify instance name'),

    @transaction.atomic
    def handle(self, *args, **options):
        instance_name = options['instance_name']
        instance = Instance.objects.get(name=instance_name)

        trees = inaturalist.get_features_for_inaturalist()

        logger.debug('{} trees to add'.format(len(trees)))
        inaturalist.create_observations(instance, tree_id=654)

        for tree in trees:
            try:
                inaturalist.create_observations(instance, tree_id=tree['tree_id'])
            except Exception as e:
                logger.exception('Could not run tree_id {tree_id} plot {plot_id}'.format(**tree), e)
            pass

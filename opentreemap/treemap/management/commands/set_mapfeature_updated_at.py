# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.core.management.base import BaseCommand

from treemap.lib.map_feature import set_map_feature_updated_at


class Command(BaseCommand):
    """
    Sets the value of MapFeature.updated_at based on the content of the
    treemap_audit table
    """
    def handle(self, *args, **options):
        print('If you have a large database, the queries run by this command '
              'may take a while to complete')
        set_map_feature_updated_at()

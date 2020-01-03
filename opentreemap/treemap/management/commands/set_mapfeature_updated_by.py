# -*- coding: utf-8 -*-




from django.core.management.base import BaseCommand

from treemap.lib.map_feature import set_map_feature_updated_by


class Command(BaseCommand):
    """
    Sets the value of MapFeature.updated_by based on the content of the
    treemap_audit table.

    Run this command after migration `0038_updated_by`, before the
    subsequent migration that removes nullable.
    """
    def handle(self, *args, **options):
        print('If you have a large database, the queries run by this command '
              'may take a while to complete')
        set_map_feature_updated_by()

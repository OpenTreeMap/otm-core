# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from django.contrib.gis.geos import GEOSGeometry, Point

from treemap.models import MapFeaturePhoto

from django.conf import settings

logger = logging.getLogger('')


class Command(BaseCommand):
    """
    Migrate all images from the file
    """

    def add_arguments(self, parser):
        pass

    @transaction.atomic
    def handle(self, *args, **options):
        photos = MapFeaturePhoto.objects.all()

        for photo in photos:
            try:
                filename = '{}/{}'.format(settings.MEDIA_ROOT, photo.image.name)
                with open(filename) as image:
                    photos.set_image(image)
                photos.save()
                logger.info("Migrated id {}".format(photo.id))
            except Exception as e:
                logger.exception("Could not load id {}, {}".format(photo.id, filename))

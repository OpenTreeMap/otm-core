# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.core.management.base import BaseCommand

from treemap.models import Instance, MapFeaturePhoto


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--instance-url-name',
            action='store',
            dest='instance_url_name',
            help='Specify the instance to add trees to'),

    def handle(self, *args, **options):
        """
        Write a csv to stdout with a row for each MapFeaturePhoto
        map_feature_id,tree_id,photo_url
        """
        if options['instance_url_name']:
            instance = Instance.objects.get(
                url_name=options['instance_url_name'])
        else:
            raise Exception("must provide instance")

        photos = MapFeaturePhoto.objects.filter(instance=instance)
        for p in photos.order_by('map_feature_id',
                                 'treephoto__tree_id',
                                 'created_at'):
            url = p.image.url
            if url[:4] == 'http' and '?' in url:
                # The S3 backend generates URLs with signatures but all OTM
                # photos are publicly accessible. We remove the query
                # string so that we don't have to worry about the
                # signatures timing out.
                url = url[:url.index('?')]
            row = [str(p.map_feature_id),
                   str(p.treephoto.tree_id),
                   '"' + url + '"']
            print(','.join(row))

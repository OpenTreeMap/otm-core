# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import csv
import logging
from tempfile import TemporaryFile

from django.core.management.base import BaseCommand
from django.db import transaction

from django.contrib.gis.geos import GEOSGeometry, Point

from treemap.instance import (Instance, InstanceBounds,
                              create_stewardship_udfs,
                              add_species_to_instance)
from treemap.models import (InstanceUser, User, NeighborhoodGroup)
from treemap.audit import (Role, FieldPermission, add_default_permissions,
                           add_instance_permissions)

from exporter.group import write_groups

# FIXME should this be an InstanceGroup? With only one instance, no need
from django.contrib.auth.models import Group


logger = logging.getLogger('')


class Command(BaseCommand):
    """
    Create a new instance with a single editing role.
    """
    def add_arguments(self, parser):
        parser.add_argument(
            'instance_name',
            help='Specify instance name'),
        parser.add_argument(
            '--filename',
            dest='filename',
            help='File for setting up groups'),
        parser.add_argument(
            '--report',
            action='store_true',
            dest='report',
            help='Run a sample report'),

    @transaction.atomic
    def handle(self, *args, **options):
        instance_name = options['instance_name']
        instance = Instance.objects.get(name=instance_name)

        if options.get('report'):
            self.run_report(instance)
            return

        filename = options['filename']
        with open(filename, mode='r') as csv_file:
            csv_reader = csv.DictReader(csv_file)
            line_count = 0
            for row in csv_reader:
                try:
                    user = User.objects.get(email=row['Email'])
                except:
                    continue
                group, _ = NeighborhoodGroup.objects.get_or_create(
                    name='{} - {}'.format(row['Ward'], row['Neighborhood']),
                    ward=row['Ward'],
                    neighborhood=row['Neighborhood']
                )
                group.user_set.add(user)
                group.save()

    def run_report(self, instance):
        filename = 'groups.csv'
        file_obj = TemporaryFile()
        write_groups(file_obj, instance)

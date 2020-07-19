# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from django.contrib.gis.geos import GEOSGeometry, Point

from treemap.instance import (Instance, InstanceBounds,
                              create_stewardship_udfs,
                              add_species_to_instance)
from treemap.models import (InstanceUser, User, NeighborhoodGroup)
from treemap.audit import (Role, FieldPermission, add_default_permissions,
                           add_instance_permissions)

# FIXME should this be an InstanceGroup? With only one instance, no need
from django.contrib.auth.models import Group


logger = logging.getLogger('')


class Command(BaseCommand):
    """
    Create a new instance with a single editing role.
    """

    """
    def add_arguments(self, parser):
        parser.add_argument(
            'instance_name',
            help='Specify instance name'),
        parser.add_argument(
            '--user',
            required=True,
            dest='user',
            help='Specify admin user name'),
        parser.add_argument(
            '--center',
            dest='center',
            help='Specify the center of the map as a lon,lat pair'),
        parser.add_argument(
            '--geojson',
            dest='geojson',
            help=('Specify a boundary via a geojson file. Must be '
                  'projected in EPSG:4326')),
        parser.add_argument(
            '--url_name',
            required=True,
            dest='url_name',
            help=('Specify a "url_name" starting with a lowercase letter and '
                  'containing lowercase letters, numbers, and dashes ("-")'))
    """

    @transaction.atomic
    def handle(self, *args, **options):

        even_group, _ = NeighborhoodGroup.objects.get_or_create(
            name='Even Group',
            ward='Even Ward',
            neighborhood='Even Neighborhood'
        )

        odd_group, _ = NeighborhoodGroup.objects.get_or_create(
            name='Odd Group',
            ward='Odd Ward',
            neighborhood='Odd Neighborhood'
        )

        #user = User.objects.get(username='tzinckgraf')
        # list of highest contributing users
        user_ids = [12, 46, 57, 75, 23, 82, 40]
        users = User.objects.filter(id__in=user_ids)

        for user in users:
            group = even_group if user.id % 2 == 0 else odd_group
            group.user_set.add(user)

        even_group.save()
        odd_group.save()
        #test_group.user_set.add(user)
        #test_group.save()

        import ipdb; ipdb.set_trace() # BREAKPOINT
        pass



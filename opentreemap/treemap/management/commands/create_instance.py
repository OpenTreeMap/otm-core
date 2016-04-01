# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import logging
from optparse import make_option

from django.core.management.base import BaseCommand
from django.db import transaction

from django.contrib.gis.geos import GEOSGeometry, Point

from treemap.instance import (Instance, InstanceBounds,
                              create_stewardship_udfs,
                              add_species_to_instance)
from treemap.models import (Boundary, InstanceUser, User,
                            BenefitCurrencyConversion)
from treemap.audit import (Role, FieldPermission, add_default_permissions)

logger = logging.getLogger('')


class Command(BaseCommand):
    """
    Create a new instance with a single editing role.
    """

    option_list = BaseCommand.option_list + (
        make_option('--user',
                    dest='user',
                    help='Specify admin user name'),
        make_option('--center',
                    dest='center',
                    help='Specify the center of the map as a lon,lat pair'),
        make_option('--geojson',
                    dest='geojson',
                    help=('Specify a boundary via a geojson file. Must be '
                          'projected in EPSG:4326')),
        make_option('--url_name',
                    dest='url_name',
                    help=('Specify a "url_name" starting with a '
                          'lowercase letter and containing lowercase '
                          'letters, numbers, and dashes ("-")'))
    )

    @transaction.atomic
    def handle(self, *args, **options):
        if len(args) != 1:
            raise Exception(
                'Expected instance name as the first argument')

        name = args[0]

        if not options['user']:
            raise Exception('An admin user must be specified. with "--user"')

        if options.get('center', None) and options.get('geojson', None):
            raise Exception('You must specifiy only one of '
                            '"center" and "geojson"')
        elif (not options.get('center', None) and
              not options.get('geojson', None)):
            raise Exception('You must specifiy at least one of '
                            '"center" and "geojson"')

        if options['center']:
            center = options['center'].split(',')
            if len(center) != 2:
                raise Exception('Center should be a lon,lat pair')

            center_pt = Point(float(center[0]), float(center[1]), srid=4326)

            # Bounding box built in web mercator to have units in meters
            center_pt.transform(3857)
            x = center_pt.x
            y = center_pt.y
            instance_bounds = InstanceBounds.create_from_point(x, y)
        else:
            geom = GEOSGeometry(open(options['geojson'], srid=4326).read())
            instance_bounds = InstanceBounds.objects.create(geom=geom)

        if not options.get('url_name', None):
            raise Exception('You must specify a "url_name" starting with a '
                            'lowercase letter and containing lowercase '
                            'letters, numbers, and dashes ("-")')
        url_name = options.get('url_name')

        instance = Instance(
            config={},
            name=name,
            bounds=instance_bounds,
            is_public=True,
            url_name=url_name)

        instance.seed_with_dummy_default_role()
        instance.full_clean()
        instance.save()

        instance.boundaries = Boundary.objects.filter(
            geom__intersects=instance_bounds.geom)

        role = Role.objects.create(
            name='user', instance=instance, rep_thresh=0,
            default_permission=FieldPermission.WRITE_DIRECTLY)

        create_stewardship_udfs(instance)

        add_species_to_instance(instance)

        add_default_permissions(instance, roles=[role])

        eco_benefits_conversion = \
            BenefitCurrencyConversion.get_default_for_point(Point(x, y))
        if eco_benefits_conversion:
            eco_benefits_conversion.save()

        instance.eco_benefits_conversion = eco_benefits_conversion

        instance.default_role = role
        instance.save()

        user = User.objects.get(username=options['user'])
        InstanceUser(
            instance=instance,
            user=user,
            role=role,
            admin=True).save_with_user(user)

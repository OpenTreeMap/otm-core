# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import csv
import json
import requests
import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from django.contrib.gis.utils import LayerMapping

from django.contrib.gis.db import models
from django.contrib.gis.geos import GEOSGeometry, Point, MultiPolygon

from treemap.instance import (Instance, InstanceBounds,
                              create_stewardship_udfs,
                              add_species_to_instance)
from treemap.models import (Boundary, InstanceUser, User,
                            BenefitCurrencyConversion)
from treemap.audit import (Role, FieldPermission, add_default_permissions,
                           add_instance_permissions)

logger = logging.getLogger('')


class JCNeighborhoodsOTM(models.Model):
    nghbhd = models.CharField(max_length=50)
    main_nghbh = models.CharField(max_length=25)
    geom = models.MultiPolygonField(srid=4326)


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
            help=('Specify a boundary via a geojson file. Must be '
                  'projected in EPSG:4326')),
        parser.add_argument(
            '--park',
            action='store_true',
            help='Is a parks file from JC OpenData website'),

    @transaction.atomic
    def handle(self, *args, **options):
        instance_name = options['instance_name']
        instance = Instance.objects.get(name=instance_name)

        #self.create_neighborhoods(instance)
        self.create_park_boundary(instance)


    def create_park_boundary(self, instance):

        url = 'https://data.jerseycitynj.gov/api/records/1.0/search/?rows={rows}&location=13,40.72164,-74.06642&basemap=jawg.light&start={start}&fields=park,govt,area,acre,geo_point_2d,geo_shape&dataset=jersey-city-parks-map&timezone=America%2FNew_York&lang=en'
        row_count = 20
        offset = 0

        records = []

        while True:
            request = requests.get(url.format(rows=row_count, start=offset))
            if not request.ok:
                raise Exception('Problem with request')
                break

            records_request = request.json()['records']
            records.extend(records_request)

            if not records_request:
                break

            offset += len(records_request)

        boundaries = []
        for record in records:
            fields = record['fields']
            geojson = '{}'.format(fields['geo_shape'])
            geom = GEOSGeometry(json.dumps(fields['geo_shape']), srid=4326)
            if geom.geom_type == 'Polygon':
                geom = MultiPolygon(geom, srid=4326)
            boundary = Boundary(
                geom=geom,
                name=fields.get('park', 'Missing Name'),
                category='Park',
                searchable=True,
                sort_order=0
            )
            boundaries.append(boundary)

        """
        ** query for turning this into a GeoJSON file

        SELECT row_to_json(fc)
        FROM (
            SELECT 'FeatureCollection' As type, array_to_json(array_agg(f)) As features
            FROM (
                SELECT  'Feature' As type
                        , ST_AsGeoJSON(ST_Transform(lg.the_geom_webmercator, 4326))::json As geometry
                        , row_to_json(lp) As properties
                FROM treemap_boundary As lg
                INNER JOIN (SELECT id, name FROM treemap_boundary) As lp
                    ON lg.id = lp.id
                where  lg.category = 'Park'
                and    lg.name ilike '%lincoln%park%'
            ) As f
        ) As fc
        """
        Boundary.objects.bulk_create(boundaries)

    def create_neighborhoods(self, instance):
        """
        python manage.py ogrinspect ~/code/opentreemap/otm-core/data/JCNeighborhoodsOTM.shp JCNeighborhoodsOTM --srid=4326 --mapping --multi
        """
        jcneighborhoodsotm_mapping = {
            'nghbhd' : 'Nghbhd',
            'main_nghbh' : 'Main_Nghbh',
            'geom' : 'MULTIPOLYGON',

        }

        shapefile = '/home/tzinckgraf/code/opentreemap/otm-core/data/JCNeighborhoodsOTM.shp'
        lm = LayerMapping(
            JCNeighborhoodsOTM,
            shapefile,
            jcneighborhoodsotm_mapping,
            transform=False
        )

        import ipdb; ipdb.set_trace() # BREAKPOINT
        pass

# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.contrib.gis.db import models

from treemap.decorators import classproperty
from treemap.models import MapFeature, GeoHStoreUDFManager
from treemap.ecobenefits import CountOnlyBenefitCalculator


class PolygonalMapFeature(MapFeature):
    area_field_name = 'polygon'
    skip_detail_form = True

    polygon = models.MultiPolygonField(srid=3857)

    objects = GeoHStoreUDFManager()

    @property
    def is_editable(self):
        # this is a holdover until we can support editing for all resources
        return True

    @classproperty
    def benefits(cls):
        return CountOnlyBenefitCalculator(cls)


class Bioswale(PolygonalMapFeature):
    objects = GeoHStoreUDFManager()

    collection_udf_defaults = {
        'Stewardship': [
            {'name': 'Action',
             'choices': ['Watered',
                         'Pruned',
                         'Mulched, Had Compost Added, or Soil Amended',
                         'Cleared of Trash or Debris'],
             'type': 'choice'},
            {'type': 'date',
             'name': 'Date'}],
    }

# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.contrib.gis.db import models
from django.utils.translation import ugettext_lazy as _

from treemap.decorators import classproperty
from treemap.models import MapFeature, GeoHStoreUDFManager
from treemap.ecobenefits import CountOnlyBenefitCalculator


class PolygonalMapFeature(MapFeature):
    area_field_name = 'polygon'
    skip_detail_form = True

    polygon = models.MultiPolygonField(srid=3857)

    objects = GeoHStoreUDFManager()

    def __init__(self, *args, **kwargs):
        super(PolygonalMapFeature, self).__init__(*args, **kwargs)
        self._do_not_track.add('polygonalmapfeature_ptr')
        self.populate_previous_state()

    @property
    def is_editable(self):
        # this is a holdover until we can support editing for all resources
        return True

    @classproperty
    def benefits(cls):
        return CountOnlyBenefitCalculator(cls)


class Bioswale(PolygonalMapFeature):
    objects = GeoHStoreUDFManager()

    udf_settings = {
        'Perennial Plants': {
            'iscollection': False,
            'defaults': {
                'type': 'multichoice',
                'choices': [
                    "Black-eyed Susan - Rudbeckia hirta",
                    "Daylily - Hemerocallis",
                    "Lobelia - Lobelia",
                    "Sedge - Carex",
                    "Switchgrass - Panicum virgatum",
                ],
            }
        },
        'Stewardship': {
            'iscollection': True,
            'range_field_key': 'Date',
            'action_field_key': 'Action',
            'action_verb': 'that have been',
            'defaults': [
                {'name': 'Action',
                 'choices': [
                     'Removed litter',
                     'Removed weeds',
                     'Pruned plants',
                     'Pruned trees',
                     'Watered bioswale',
                     'Removed sediments',
                     'Redistributed gravel',
                     'Redistributed soil',
                     'Aerated soil',
                 ],
                 'type': 'choice'},
                {'type': 'date',
                 'name': 'Date'}],
        }
    }

    @classproperty
    def search_display_name(cls):
        return _('bioswales')

    @classproperty
    def display_name(cls):
        return _('Bioswale')


class RainGarden(PolygonalMapFeature):
    objects = GeoHStoreUDFManager()

    udf_settings = {
        'Perennial Plants': {
            'iscollection': False,
            'defaults': {
                'type': 'multichoice',
                'choices': [
                    "Black-eyed Susan - Rudbeckia hirta",
                    "Daylily - Hemerocallis",
                    "Lobelia - Lobelia",
                    "Sedge - Carex",
                    "Switchgrass - Panicum virgatum",
                ],
            },
        },
    }

    @classproperty
    def search_display_name(cls):
        return _('rain gardens')

    @classproperty
    def display_name(cls):
        return _('Rain Garden')


class RainBarrel(MapFeature):
    objects = GeoHStoreUDFManager()
    capacity = models.FloatField(help_text=_("Capacity"))

    @classproperty
    def search_display_name(cls):
        return _('rain barrels')

    @classproperty
    def display_name(cls):
        return _('Rain Barrel')

    @property
    def is_editable(self):
        # this is a holdover until we can support editing for all resources
        return True

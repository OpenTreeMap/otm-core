# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.contrib.gis.db import models
from django.db import connection
from django.utils.translation import ugettext_lazy as _

from stormwater.benefits import PolygonalBasinBenefitCalculator
from treemap.decorators import classproperty
from treemap.models import MapFeature, ValidationMixin
from treemap.ecobenefits import CountOnlyBenefitCalculator


class PolygonalMapFeature(MapFeature):
    area_field_name = 'polygon'
    enable_detail_next = True

    polygon = models.MultiPolygonField(srid=3857)

    objects = models.GeoManager()

    @classproperty
    def always_writable(cls):
        return MapFeature.always_writable | {'polygon'}

    def __init__(self, *args, **kwargs):
        super(PolygonalMapFeature, self).__init__(*args, **kwargs)
        self._do_not_track |= self.do_not_track

    @classproperty
    def do_not_track(cls):
        return MapFeature.do_not_track | {'polygonalmapfeature_ptr'}

    @property
    def is_editable(self):
        # this is a holdover until we can support editing for all resources
        return True

    @classproperty
    def benefits(cls):
        return PolygonalBasinBenefitCalculator(cls)

    @classmethod
    def polygon_area(cls, polygon):
        """
        Make a PostGIS query that accurately calculates the area of
        the polygon(s) by first casting to a Geography.
        """
        with connection.cursor() as cursor:
            cursor.execute('SELECT ST_Area(ST_Transform(ST_GeomFromEWKB(%s), 4326)::geography)',  # NOQA
                           [polygon.ewkb])
            return cursor.fetchone()[0]

    @classmethod
    def feature_qs_areas(cls, polygonal_map_feature_qs):
        """
        Make a PostGIS query that accurately calculates the area of
        the polygon(s) by first casting to a Geography.
        """
        area_sql = 'ST_Area(ST_Transform(polygon, 4326)::geography)'
        area_col_name = 'area'
        feature_areas = polygonal_map_feature_qs \
            .extra(select={area_col_name: area_sql}) \
            .values_list(area_col_name, flat=True)
        return feature_areas

    @classmethod
    def field_display_name(cls, field_name):
        if field_name == 'polygon':
            # Translators: area in this context is a measurement
            return _('area')
        else:
            return field_name

    def calculate_area(self):
        if self.polygon is None:
            return None
        return PolygonalMapFeature.polygon_area(self.polygon)


class Bioswale(PolygonalMapFeature, ValidationMixin):
    objects = models.GeoManager()
    drainage_area = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Adjacent Drainage Area"),
        error_messages={'invalid': _("Please enter a number.")})

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

    _terminology = {
        'singular': _('Bioswale'),
        'plural': _('Bioswales'),
    }

    default_config = {
        'should_show_eco': False,
        'diversion_rate': 0.85
    }

    def clean(self):
        self.validate_positive_nullable_float_field('drainage_area',
                                                    zero_ok=True)
        super(Bioswale, self).clean()


class RainGarden(PolygonalMapFeature, ValidationMixin):
    objects = models.GeoManager()
    drainage_area = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Adjacent Drainage Area"),
        error_messages={'invalid': _("Please enter a number.")})

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
        },
    }

    _terminology = {
        'singular': _('Rain Garden'),
        'plural': _('Rain Gardens'),
    }

    default_config = {
        'should_show_eco': False,
        'diversion_rate': 0.85
    }

    def clean(self):
        self.validate_positive_nullable_float_field('drainage_area',
                                                    zero_ok=True)
        super(RainGarden, self).clean()


class RainBarrel(MapFeature):
    objects = models.GeoManager()
    capacity = models.FloatField(
        verbose_name=_("Capacity"),
        error_messages={'invalid': _("Please enter a number.")})

    _terminology = {
        'singular': _('Rain Barrel'),
        'plural': _('Rain Barrels'),
    }

    @property
    def is_editable(self):
        # this is a holdover until we can support editing for all resources
        return True

    @classproperty
    def benefits(cls):
        return CountOnlyBenefitCalculator(cls)

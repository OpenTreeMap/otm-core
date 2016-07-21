# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.utils.translation import ugettext_lazy as _

from treemap.ecobenefits import (BenefitCalculator, FEET_SQ_PER_METER_SQ,
                                 FEET_PER_INCH, GALLONS_PER_CUBIC_FT)


class PolygonalBasinBenefitCalculator(BenefitCalculator):

    def __init__(self, MapFeatureClass):
        self.MapFeatureClass = MapFeatureClass

    def benefits_for_filter(self, instance, item_filter):
        features_qs = item_filter.get_objects(self.MapFeatureClass)
        return self._benefits_for_feature_qs(features_qs, instance)

    def benefits_for_object(self, instance, feature):
        from stormwater.models import PolygonalMapFeature
        feature_qs = PolygonalMapFeature.objects.filter(pk=feature.pk)
        stats, basis = self._benefits_for_feature_qs(feature_qs, instance)
        return stats, basis, None

    def _benefits_for_feature_qs(self, feature_qs, instance):
        annual_rainfall_ft = instance.annual_rainfall_inches * FEET_PER_INCH
        config = self.MapFeatureClass.get_config(instance)
        diversion_rate = config['diversion_rate']
        should_compute = (annual_rainfall_ft is not None and
                          diversion_rate is not None and
                          config['should_show_eco'])
        if should_compute:
            # annual stormwater diverted =
            #     annual rainfall x area x fraction stormwater diverted
            feature_areas = \
                self.MapFeatureClass.feature_qs_areas(feature_qs)
            total_area = sum(feature_areas) * FEET_SQ_PER_METER_SQ
            runoff_reduced = annual_rainfall_ft * total_area * diversion_rate
            runoff_reduced *= GALLONS_PER_CUBIC_FT
            stats = self._format_stats(instance, runoff_reduced)
            basis = self._get_basis(feature_qs.count(), 0)
        else:
            stats = {}
            basis = self._get_basis(0, feature_qs.count())
        return stats, basis

    def _format_stats(self, instance, runoff_reduced):
        factor_conversions = instance.eco_benefits_conversion
        if factor_conversions:
            currency = runoff_reduced * factor_conversions.h20_gal_to_currency
        else:
            currency = 0

        return {
            'resource': {
                'runoff_reduced': {
                    'value': runoff_reduced,
                    'unit': 'gallons',
                    'unit-name': 'green_infrastructure_eco',
                    'currency': currency,
                    'label': _('Stormwater runoff reduced')
                }
            }
        }

    def _get_basis(self, n_calc, n_discard):
        return {
            'resource': {
                'n_objects_used': n_calc,
                'n_objects_discarded': n_discard
            }
        }

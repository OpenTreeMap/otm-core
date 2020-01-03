# -*- coding: utf-8 -*-




from django.db.models import Sum
from django.utils.translation import ugettext_lazy as _

from treemap.ecobenefits import (BenefitCalculator, FEET_SQ_PER_METER_SQ,
                                 FEET_PER_INCH, GALLONS_PER_CUBIC_FT,
                                 BenefitCategory)


class PolygonalBasinBenefitCalculator(BenefitCalculator):

    def __init__(self, MapFeatureClass):
        self.MapFeatureClass = MapFeatureClass

    def benefits_for_filter(self, instance, item_filter):
        features_qs = item_filter.get_objects(self.MapFeatureClass)
        return self._benefits_for_feature_qs(features_qs, instance)

    def benefits_for_object(self, instance, feature):
        feature_qs = feature.__class__.objects.filter(pk=feature.pk)
        stats, basis = self._benefits_for_feature_qs(feature_qs, instance)
        return stats, basis, None

    def _benefits_for_feature_qs(self, feature_qs, instance):
        from stormwater.models import PolygonalMapFeature
        feature_count = feature_qs.count()
        feature_qs = feature_qs.filter(drainage_area__isnull=False)
        poly_qs = PolygonalMapFeature.objects.filter(id__in=feature_qs)
        config = self.MapFeatureClass.get_config(instance)
        diversion_rate = config['diversion_rate']
        should_compute = (instance.annual_rainfall_inches is not None and
                          diversion_rate is not None and
                          config['should_show_eco'])
        if should_compute:
            total_drainage_area = feature_qs.aggregate(
                total_drainage_area=Sum('drainage_area')).get(
                'total_drainage_area')
            if total_drainage_area is None:
                should_compute = False
        if should_compute:
            annual_rainfall_ft = instance.annual_rainfall_inches * \
                FEET_PER_INCH
            # annual stormwater diverted =
            #     annual rainfall x (total feature area +
            #     (total drainage area x fraction stormwater diverted))
            total_drainage_area *= FEET_SQ_PER_METER_SQ
            feature_areas = \
                self.MapFeatureClass.feature_qs_areas(poly_qs)
            total_area = sum(feature_areas) * FEET_SQ_PER_METER_SQ
            runoff_reduced = annual_rainfall_ft * (
                total_area + total_drainage_area * diversion_rate)
            runoff_reduced *= GALLONS_PER_CUBIC_FT
            stats = self._format_stats(instance, runoff_reduced)
            features_used = poly_qs.count()
            basis = self._get_basis(features_used,
                                    feature_count - features_used)
        else:
            stats = {}
            basis = self._get_basis(0, feature_count)
        return stats, basis

    def _format_stats(self, instance, runoff_reduced):
        factor_conversions = instance.eco_benefits_conversion
        if factor_conversions:
            currency = runoff_reduced * factor_conversions.h20_gal_to_currency
        else:
            currency = 0

        return {
            'resource': {
                BenefitCategory.STORMWATER: {
                    'value': runoff_reduced,
                    'unit': 'gallons',
                    'unit-name': 'eco',
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

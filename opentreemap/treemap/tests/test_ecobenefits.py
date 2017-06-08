# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json

from unittest.case import skip

from django.core.cache import cache
from django.test import override_settings

from treemap.models import (Plot, Tree, Species, ITreeRegion,
                            ITreeCodeOverride, BenefitCurrencyConversion)
from treemap.tests import (make_instance, make_commander_user, make_request,
                           OTMTestCase)
from treemap.tests.test_urls import UrlTestCase

from treemap import ecobackend
from treemap.ecobenefits import (TreeBenefitsCalculator,
                                 _combine_benefit_basis,
                                 _annotate_basis_with_extra_stats,
                                 _combine_grouped_benefits, BenefitCategory)
from treemap.views.tree import search_tree_benefits
from treemap.search import Filter
from treemap.ecocache import (get_cached_benefits, get_cached_plot_count,
                              invalidate_ecoservice_cache_if_stale)


class EcoTestCase(UrlTestCase):
    def setUp(self):
        # Example url for
        # CEAT, 1630 dbh, NoEastXXX
        # eco.json?otmcode=CEAT&diameter=1630&region=NoEastXXX
        def mockbenefits(*args, **kwargs):
            benefits = {
                "Benefits": {
                    "aq_nox_avoided": 0.6792,
                    "aq_nox_dep": 0.371,
                    "aq_ozone_dep": 0.775,
                    "aq_pm10_avoided": 0.0436,
                    "aq_pm10_dep": 0.491,
                    "aq_sox_avoided": 0.372,
                    "aq_sox_dep": 0.21,
                    "aq_voc_avoided": 0.0254,
                    "bvoc": -0.077,
                    "co2_avoided": 255.5,
                    "co2_sequestered": 0,
                    "co2_storage": 6575,
                    "electricity": 187,
                    "hydro_interception": 12.06,
                    "natural_gas": 5834.1
                }
            }
            return (benefits, None)

        region = ITreeRegion.objects.get(code='NoEastXXX')
        p = region.geometry.point_on_surface

        converter = BenefitCurrencyConversion(
            currency_symbol='$',
            electricity_kwh_to_currency=1.0,
            natural_gas_kbtu_to_currency=1.0,
            co2_lb_to_currency=1.0,
            o3_lb_to_currency=1.0,
            nox_lb_to_currency=1.0,
            pm10_lb_to_currency=1.0,
            sox_lb_to_currency=1.0,
            voc_lb_to_currency=1.0,
            h20_gal_to_currency=1.0)
        converter.save()

        self.instance = make_instance(is_public=True, point=p)
        self.instance.eco_benefits_conversion = converter
        self.instance.save()
        self.user = make_commander_user(self.instance)

        self.species = Species(otm_code='CEAT',
                               genus='cedrus',
                               species='atlantica',
                               max_diameter=2000,
                               max_height=100,
                               instance=self.instance)

        self.species.save_with_user(self.user)

        self.origBenefitFn = ecobackend.json_benefits_call
        ecobackend.json_benefits_call = mockbenefits

    def tearDown(self):
        ecobackend.json_benefits_call = self.origBenefitFn

    def assert_benefit_value(self, bens, benefit, unit, value):
        self.assertEqual(bens[benefit]['unit'], unit)
        self.assertEqual(int(float(bens[benefit]['value'])), value)


class EcoTest(EcoTestCase):
    def setUp(self):
        super(EcoTest, self).setUp()
        p = self.instance.center
        self.plot = Plot(geom=p, instance=self.instance)

        self.plot.save_with_user(self.user)

        self.tree = Tree(plot=self.plot,
                         instance=self.instance,
                         readonly=False,
                         species=self.species,
                         diameter=1630)

        self.tree.save_with_user(self.user)

    def test_eco_benefit_sanity(self):
        rslt, basis, error = TreeBenefitsCalculator()\
            .benefits_for_object(self.instance, self.tree.plot)

        bens = rslt['plot']

        self.assert_benefit_value(bens, BenefitCategory.ENERGY, 'kwh', 1896)
        self.assert_benefit_value(bens, BenefitCategory.AIRQUALITY,
                                  'lbs', 6)
        self.assert_benefit_value(bens, BenefitCategory.STORMWATER,
                                  'gal', 3185)
        self.assert_benefit_value(bens, BenefitCategory.CO2, 'lbs', 563)
        self.assert_benefit_value(bens, BenefitCategory.CO2STORAGE,
                                  'lbs', 6575)

    def testSearchBenefits(self):
        request = make_request(
            {'q': json.dumps({'tree.readonly': {'IS': False}})})  # all trees
        request.instance_supports_ecobenefits = self.instance\
                                                    .has_itree_region()
        result = search_tree_benefits(request, self.instance)

        benefits = result['benefits']

        self.assertTrue(len(benefits) > 0)

    def test_group_basis_empty(self):
        basis = {}
        example = {
            'group1': {
                'n_objects_used': 5,
                'n_objects_discarded': 8
            },
            'group2': {
                'n_objects_used': 10,
                'n_objects_discarded': 12
            }
        }

        _combine_benefit_basis(basis, example)
        self.assertEqual(basis, example)

    def test_group_basis_combine_new_group(self):
        # New groups are added
        basis = {
            'group1': {
                'n_objects_used': 5,
                'n_objects_discarded': 8
            }
        }
        new_group = {
            'group2': {
                'n_objects_used': 13,
                'n_objects_discarded': 4
            }
        }
        target = {
            'group1': {
                'n_objects_used': 5,
                'n_objects_discarded': 8
            },
            'group2': {
                'n_objects_used': 13,
                'n_objects_discarded': 4
            }
        }
        _combine_benefit_basis(basis, new_group)
        self.assertEqual(basis, target)

    def test_group_basis_combine_existing_groups(self):
        basis = {
            'group1': {
                'n_objects_used': 5,
                'n_objects_discarded': 8
            }
        }
        update_group = {
            'group1': {
                'n_objects_used': 13,
                'n_objects_discarded': 4
            }
        }
        target = {
            'group1': {
                'n_objects_used': 18,
                'n_objects_discarded': 12
            }
        }
        _combine_benefit_basis(basis, update_group)
        self.assertEqual(basis, target)

    def test_combine_benefit_groups_empty(self):
        # with and without currency
        base_group = {'group1':
                      {'benefit1':
                       {'value': 3,
                        'currency': 9,
                        'unit': 'gal',
                        'label': BenefitCategory.STORMWATER,
                        'unit-name': 'eco'},
                       'benefit2':
                       {'value': 3,
                        'currency': 9,
                        'unit': 'gal',
                        'label': BenefitCategory.STORMWATER,
                        'unit-name': 'eco'}}}
        groups = {}
        _combine_grouped_benefits(groups, base_group)

        self.assertEqual(groups, base_group)

    def test_combine_benefit_groups_no_overlap(self):
        base_group = {'group1':
                      {'benefit1':
                       {'value': 3,
                        'currency': 9,
                        'unit': 'gal',
                        'label': BenefitCategory.STORMWATER,
                        'unit-name': 'eco'},
                       'benefit2':
                       {'value': 4,
                        'currency': 10,
                        'unit': 'gal',
                        'label': BenefitCategory.STORMWATER,
                        'unit-name': 'eco'}}}
        new_group = {'group2':
                     {'benefit1':
                      {'value': 5,
                       'currency': 11,
                       'unit': 'gal',
                       'label': BenefitCategory.STORMWATER,
                       'unit-name': 'eco'},
                      'benefit2':
                      {'value': 6,
                       'currency': 19,
                       'unit': 'gal',
                       'label': BenefitCategory.STORMWATER,
                       'unit-name': 'eco'}}}
        groups = {}
        _combine_grouped_benefits(groups, base_group)
        _combine_grouped_benefits(groups, new_group)

        target = {'group1': base_group['group1'],
                  'group2': new_group['group2']}

        self.assertEqual(groups, target)

    def test_combine_benefit_groups_sums_benefits(self):
        base_group = {'group1':
                      {'benefit1':
                       {'value': 3,
                        'unit': 'gal',
                        'label': BenefitCategory.STORMWATER,
                        'unit-name': 'eco'},
                       'benefit2':
                       {'value': 4,
                        'currency': 10,
                        'unit': 'gal',
                        'label': BenefitCategory.STORMWATER,
                        'unit-name': 'eco'},
                       'benefit3':
                       {'value': 32,
                        'currency': 919,
                        'unit': 'gal',
                        'label': BenefitCategory.STORMWATER,
                        'unit-name': 'eco'}}}
        new_group = {'group1':
                     {'benefit1':
                      {'value': 5,
                       'currency': 11,
                       'unit': 'gal',
                       'label': BenefitCategory.STORMWATER,
                       'unit-name': 'eco'},
                      'benefit2':
                      {'value': 7,
                       'unit': 'gal',
                       'currency': 19,
                       'label': BenefitCategory.STORMWATER,
                       'unit-name': 'eco'},
                      'benefit4':
                      {'value': 7,
                       'unit': 'gal',
                       'label': BenefitCategory.STORMWATER,
                       'unit-name': 'eco'}}}
        groups = {}
        _combine_grouped_benefits(groups, base_group)
        _combine_grouped_benefits(groups, new_group)

        target = {'group1':
                  {'benefit1':
                   {'value': 8,
                    'currency': 11,
                    'unit': 'gal',
                    'label': BenefitCategory.STORMWATER,
                    'unit-name': 'eco'},
                   'benefit2':
                   {'value': 11,
                    'currency': 29,
                    'unit': 'gal',
                    'label': BenefitCategory.STORMWATER,
                    'unit-name': 'eco'},
                   'benefit3':
                   {'value': 32,
                    'currency': 919,
                    'unit': 'gal',
                    'label': BenefitCategory.STORMWATER,
                    'unit-name': 'eco'},
                   'benefit4':
                   {'value': 7,
                    'unit': 'gal',
                    'label': BenefitCategory.STORMWATER,
                    'unit-name': 'eco'}}}

        self.assertEqual(groups, target)

    def test_annotates_basis(self):
        basis = {
            'group1': {
                'n_objects_used': 5,
                'n_objects_discarded': 15
            },
            'group2': {
                'n_objects_used': 2,
                'n_objects_discarded': 18
            }
        }
        target = {
            'group1': {
                'n_objects_used': 5,
                'n_objects_discarded': 15,
                'n_total': 20,
                'n_pct_calculated': 0.25
            },
            'group2': {
                'n_objects_used': 2,
                'n_objects_discarded': 18,
                'n_total': 20,
                'n_pct_calculated': 0.1
            }
        }
        _annotate_basis_with_extra_stats(basis)

        self.assertEqual(basis, target)


@override_settings(USE_ECO_CACHE=True)
class EcoCacheTest(UrlTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.user = make_commander_user(self.instance)
        self.benefits = 'some benefits'
        self.filter = Filter('', '', self.instance)

    def tearDown(self):
        cache.clear()

    def get_cached_tree_benefits(self, filter, fn):
        return get_cached_benefits('Plot', filter, fn)

    def test_benefits_are_cached(self):
        self.get_cached_tree_benefits(self.filter, lambda: self.benefits)
        benefits = self.get_cached_tree_benefits(self.filter, lambda: 'others')
        self.assertEqual(benefits, self.benefits)

    def test_updating_eco_rev_busts_benefit_cache(self):
        self.get_cached_tree_benefits(self.filter, lambda: self.benefits)
        self.filter.instance.update_eco_rev()
        benefits = self.get_cached_tree_benefits(self.filter, lambda: 'others')
        self.assertEqual(benefits, 'others')

    def test_count_is_cached(self):
        count = get_cached_plot_count(self.filter)
        self.assertEqual(0, count)

        # We save with the old
        plot = Plot(geom=self.instance.center, instance=self.instance)
        plot.save_with_user(self.user)

        count = get_cached_plot_count(self.filter)
        self.assertEqual(0, count)

    def test_updating_geo_rev_busts_count_cache(self):
        count = get_cached_plot_count(self.filter)
        self.assertEqual(0, count)

        plot = Plot(geom=self.instance.center, instance=self.instance)
        plot.save_with_user(self.user)
        self.filter.instance.update_geo_rev()

        count = get_cached_plot_count(self.filter)
        self.assertEqual(1, count)


class EcoserviceCacheBusterTest(OTMTestCase):
    def setUp(self):
        def mock_json_benefits_call(*args, **kwargs):
            if args[0] == 'invalidate_cache':
                self.cache_invalidated = True
            return None, None

        self.cache_invalidated = False
        self.orig_benefit_fn = ecobackend.json_benefits_call
        ecobackend.json_benefits_call = mock_json_benefits_call

    def tearDown(self):
        ecobackend.json_benefits_call = self.orig_benefit_fn

    @skip('See issue #3027')
    def test_adding_override_invalidates_cache(self):
        instance = make_instance()
        user = make_commander_user(instance)
        species = Species(instance=instance, genus='g')
        species.save_with_user(user)
        species.refresh_from_db()
        ITreeCodeOverride(
            instance_species=species,
            region=ITreeRegion.objects.get(code='NMtnPrFNL'),
            itree_code='CEL OTHER'
        ).save_with_user(user)

        invalidate_ecoservice_cache_if_stale()

        self.assertTrue(self.cache_invalidated)

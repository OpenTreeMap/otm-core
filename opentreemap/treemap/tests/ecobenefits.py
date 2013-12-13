# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.test.client import RequestFactory
from django.contrib.gis.geos import Point
from unittest import TestCase

from treemap.models import Plot, Tree, Species, ITreeRegion, ITreeCodeOverride
from treemap.tests import (UrlTestCase, make_instance, make_commander_user,
                           delete_all_app_users)

from treemap.ecobenefits import (tree_benefits, within_itree_regions,
                                 species_codes_for_regions,
                                 itree_code_for_species_in_region)


class EcoTest(UrlTestCase):
    def setUp(self):
        region = ITreeRegion.objects.get(code='NoEastXXX')
        p = region.geometry.point_on_surface

        self.instance = make_instance(is_public=True, point=p)

        self.user = make_commander_user(self.instance)

        self.species = Species(otm_code='CEAT',
                               genus='cedrus',
                               species='atlantica',
                               max_dbh=2000,
                               max_height=100,
                               instance=self.instance)
        self.species.save_with_user(self.user)

        self.plot = Plot(geom=p, instance=self.instance)

        self.plot.save_with_user(self.user)

        self.tree = Tree(plot=self.plot,
                         instance=self.instance,
                         readonly=False,
                         species=self.species,
                         diameter=1630)

        self.tree.save_with_user(self.user)

    def test_group_eco(self):
        pass  # TODO: Once filtering has been enabled

    def assert_benefit_value(self, bens, benefit, unit, value):
            self.assertEqual(bens[benefit]['unit'], unit)
            self.assertEqual(int(float(bens[benefit]['value'])), value)

    def test_eco_benefit_sanity(self):
        rslt = tree_benefits(instance=self.instance,
                             tree_id=self.tree.pk)

        bens = rslt['benefits'][0]

        self.assert_benefit_value(bens, 'energy', 'kwh', 1896)
        self.assert_benefit_value(bens, 'airquality', 'lbs/year', 6)
        self.assert_benefit_value(bens, 'stormwater', 'gal', 3185)
        self.assert_benefit_value(bens, 'co2', 'lbs/year', 563)

    def test_species_for_none_region_lookup(self):
        self.assertIsNone(species_codes_for_regions(None))

    def test_species_for_region_lookup(self):
        northeast = species_codes_for_regions(['NoEastXXX'])
        self.assertEqual(258, len(northeast))

        south = species_codes_for_regions(['PiedmtCLT'])
        self.assertEqual(244, len(south))

        combined = species_codes_for_regions(['NoEastXXX', 'PiedmtCLT'])
        self.assertEqual(338, len(combined))

        combined_set = set(combined)
        self.assertEqual(len(combined), len(combined_set),
                         "Getting the species for more than one region "
                         "should result in a unique set of otm_codes")

    def test_default_region(self):
        # move the point outside the eco region
        self.plot.geom = Point(0, 0)
        self.plot.save_with_user(self.user)

        result = tree_benefits(instance=self.instance,
                               tree_id=self.tree.pk)
        bens_wo_default = result['benefits'][0]
        self.assert_benefit_value(bens_wo_default, 'energy', 'kwh', 0)
        self.assert_benefit_value(bens_wo_default, 'airquality', 'lbs/year', 0)
        self.assert_benefit_value(bens_wo_default, 'stormwater', 'gal', 0)
        self.assert_benefit_value(bens_wo_default, 'co2', 'lbs/year', 0)

        self.instance.itree_region_default = 'NoEastXXX'
        self.instance.save()
        result = tree_benefits(instance=self.instance,
                               tree_id=self.tree.pk)
        bens_with_default = result['benefits'][0]
        self.assert_benefit_value(bens_with_default,
                                  'energy', 'kwh', 1896)
        self.assert_benefit_value(bens_with_default,
                                  'airquality', 'lbs/year', 6)
        self.assert_benefit_value(bens_with_default,
                                  'stormwater', 'gal', 3185)
        self.assert_benefit_value(bens_with_default,
                                  'co2', 'lbs/year', 563)


class WithinITreeRegionsTest(TestCase):

    def assertViewPerformsCorrectly(self, x, y, expected_value):
        params = {'x': str(x), 'y': str(y)}
        request = RequestFactory().get('', params)
        self.assertEqual(within_itree_regions(request), expected_value)

    def test_within_itree_regions_valid(self):
        region = ITreeRegion.objects.get(code='NoEastXXX')
        p = region.geometry.point_on_surface
        self.assertViewPerformsCorrectly(p.x, p.y, True)

    def test_within_itree_regions_no_overlap(self):
        self.assertViewPerformsCorrectly(0, 0, False)


class ITreeCodeForSpeciesInRegionTest(TestCase):

    def setUp(self):
        self.instance = make_instance()
        self.commander = make_commander_user(self.instance)
        self.region = ITreeRegion.objects.get(code='PiedmtCLT')

    def tearDown(self):
        delete_all_app_users()

    def make_species(self, otm_code):
        species = Species(instance=self.instance, otm_code=otm_code)
        species.save_with_user(self.commander)
        return species

    def assert_itree_code(self, species, expected_itree_code):
        itree_code = itree_code_for_species_in_region(species, self.region)
        self.assertEqual(itree_code, expected_itree_code)

    def test_no_override(self):
        species = self.make_species('CEAT')
        self.assert_itree_code(species, 'CEM OTHER')

    def test_override(self):
        species = self.make_species('ACRU')
        ITreeCodeOverride(
            instance_species=species,
            region=self.region,
            itree_code='BDM OTHER').save_with_user(self.commander)
        self.assert_itree_code(species, 'BDM OTHER')

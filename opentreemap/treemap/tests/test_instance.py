# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from treemap.instance import add_species_to_instance
from treemap.models import ITreeRegion
from treemap.species import SPECIES
from treemap.species.codes import species_codes_for_regions
from treemap.tests.base import OTMTestCase
from treemap.tests import make_instance


class AddSpeciesToInstanceTests(OTMTestCase):
    def _assert_right_species_for_region(self, instance):
        add_species_to_instance(instance)
        self.assertNotEqual(len(SPECIES),
                            len(instance.species_set.all()))
        otm_codes = species_codes_for_regions(['NoEastXXX'])
        self.assertEqual(len(otm_codes), len(instance.species_set.all()))

    def test_adds_species_based_on_itree_region(self):
        region = ITreeRegion.objects.get(code='NoEastXXX')
        instance = make_instance(point=region.geometry.point_on_surface)
        self._assert_right_species_for_region(instance)

    def test_adds_species_based_on_default_itree_region(self):
        instance = make_instance()
        instance.itree_region_default = 'NoEastXXX'
        self._assert_right_species_for_region(instance)

    def test_all_species_added_when_no_itree_region(self):
        instance = make_instance()
        add_species_to_instance(instance)
        self.assertEqual(len(SPECIES), len(instance.species_set.all()))

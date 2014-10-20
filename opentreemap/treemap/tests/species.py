# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from treemap.tests.base import OTMTestCase
from treemap.species import species_for_otm_code


class SpeciesTests(OTMTestCase):
    """Test species lookup utility functions."""

    def test_species_for_otm_code(self):
        species = species_for_otm_code('ABAL')
        self.assertEqual(species['common_name'], 'Silver fir')

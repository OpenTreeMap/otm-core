# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from treemap.tests.base import OTMTestCase
from treemap.species import otm_code_search, species_search


class SpeciesTests(OTMTestCase):
    """Test species lookup utility functions."""

    def test_otm_code_search(self):
        candidate = dict(
            genus='Abies',
            species='alba',
            cultivar='',
            other_part_in_name=''
        )
        otm_code = otm_code_search(candidate)
        self.assertEqual(otm_code, 'ABAL')

    def test_species_search(self):
        species = species_search('ABAL')
        self.assertEqual(species['common_name'], 'Silver fir')

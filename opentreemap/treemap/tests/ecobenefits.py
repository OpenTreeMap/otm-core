# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json

from treemap.models import Plot, Tree, Species, ITreeRegion
from treemap.tests import (UrlTestCase, make_instance, make_commander_user,
                           make_request)

from treemap import ecobackend
from treemap.ecobenefits import tree_benefits

from treemap.views import search_tree_benefits


class EcoTest(UrlTestCase):
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

        self.origBenefitFn = ecobackend.json_benefits_call
        ecobackend.json_benefits_call = mockbenefits

    def tearDown(self):
        ecobackend.json_benefits_call = self.origBenefitFn

    def assert_benefit_value(self, bens, benefit, unit, value):
        self.assertEqual(bens[benefit]['unit'], unit)
        self.assertEqual(int(float(bens[benefit]['value'])), value)

    def test_eco_benefit_sanity(self):
        rslt = tree_benefits(instance=self.instance,
                             tree_or_tree_id=self.tree)

        bens = rslt['tree_benefits']

        self.assert_benefit_value(bens, 'energy', 'kwh', 1896)
        self.assert_benefit_value(bens, 'airquality', 'lbs/year', 6)
        self.assert_benefit_value(bens, 'stormwater', 'gal', 3185)
        self.assert_benefit_value(bens, 'co2', 'lbs/year', 563)

    def testSearchBenefits(self):
        request = make_request(
            {'q': json.dumps({'tree.readonly': {'IS': False}})})  # all trees
        request.instance_supports_ecobenefits = self.instance\
                                                    .has_itree_region()
        result = search_tree_benefits(request, self.instance)

        benefits = result['tree_benefits']

        self.assertTrue(len(benefits) > 0)

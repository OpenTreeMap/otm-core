from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.test import TestCase

from ecobenefits.views import tree_benefits
from django.test.client import RequestFactory

from treemap.models import User, Instance, Plot, Tree, Species
from django.contrib.gis.geos import Point
from treemap import tests as tm

import json


class EcoTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.instance, system_user = tm.make_instance_and_system_user()

        self.user = User(username="commander")
        self.user.save_with_user(system_user)
        self.user.roles.add(tm.make_commander_role(self.instance))

        self.species = Species(symbol='CEDR',
                               genus='cedrus',
                               species='atlantica',
                               max_dbh=2000,
                               max_height=100)
        self.species.save()

        p1 = Point(-8515941.0, 4953519.0)
        self.plot = Plot(geom=p1,
                         instance=self.instance,
                         created_by=self.user)

        self.plot.save_with_user(self.user)

        self.tree = Tree(plot=self.plot,
                         instance=self.instance,
                         readonly=False,
                         species=self.species,
                         diameter=1630,
                         created_by=self.user)

        self.tree.save_with_user(self.user)

    def test_group_eco(self):
        pass  # TODO: Once filtering has been enabled

    def test_eco_benefit_sanity(self):
        req = self.factory.get('/%s/eco/benefit/tree/%s/' %
                              (self.instance.pk, self.tree.pk))

        response = tree_benefits(req,
                                 instance_id=self.instance.pk,
                                 tree_id=self.tree.pk,
                                 region='NoEastXXX')

        self.assertEqual(response.status_code, 200)
        rslt = json.loads(response.content)

        bens = rslt['benefits']

        def assertBValue(benefit, unit, value):
            self.assertEqual(bens[benefit]['unit'], unit)
            self.assertEqual(int(float(bens[benefit]['value'])), value)

        assertBValue('energy', 'kwh', 1896)
        assertBValue('airquality', 'lbs/year', 6)
        assertBValue('stormwater', 'gal', 3185)
        assertBValue('co2', 'lbs/year', 563)

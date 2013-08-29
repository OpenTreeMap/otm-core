from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.test.client import RequestFactory
from django.contrib.gis.geos import Point, MultiPolygon

from treemap.models import Plot, Tree, Species
from treemap.tests import UrlTestCase, make_instance, make_commander_user

from ecobenefits.models import ITreeRegion
from ecobenefits.views import tree_benefits


class EcoTest(UrlTestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.instance = make_instance(is_public=True)

        self.user = make_commander_user(self.instance)

        self.species = Species(symbol='CEDR',
                               genus='cedrus',
                               species='atlantica',
                               itree_code='CEM OTHER',
                               max_dbh=2000,
                               max_height=100)
        self.species.save()

        ITreeRegion.objects.all().delete()

        p1 = Point(-8515941.0, 4953519.0)

        ITreeRegion.objects.create(
            code='NoEastXXX',
            geometry=MultiPolygon([p1.buffer(1000)]))

        self.plot = Plot(geom=p1,
                         instance=self.instance)

        self.plot.save_with_user(self.user)

        self.tree = Tree(plot=self.plot,
                         instance=self.instance,
                         readonly=False,
                         species=self.species,
                         diameter=1630)

        self.tree.save_with_user(self.user)

    def test_tree_benefits_url(self):
        self.assert_200(
            '/%s/eco/benefit/tree/%s/' % (self.instance.id, self.tree.id))

    def test_tree_benefit_url_invalid(self):
        self.assert_404(
            '/%s/eco/benefit/tree/999/' % self.instance.id)

    def test_group_eco(self):
        pass  # TODO: Once filtering has been enabled

    def test_eco_benefit_sanity(self):
        rslt = tree_benefits(instance=self.instance,
                             tree_id=self.tree.pk)

        bens = rslt['benefits'][0]

        def assertBValue(benefit, unit, value):
            self.assertEqual(bens[benefit]['unit'], unit)
            self.assertEqual(int(float(bens[benefit]['value'])), value)

        assertBValue('energy', 'kwh', 1896)
        assertBValue('airquality', 'lbs/year', 6)
        assertBValue('stormwater', 'gal', 3185)
        assertBValue('co2', 'lbs/year', 563)

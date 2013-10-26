from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.test.client import RequestFactory
from django.contrib.gis.geos import Point, MultiPolygon

from treemap.models import Plot, Tree, Species
from treemap.tests import UrlTestCase, make_instance, make_commander_user

from ecobenefits.models import ITreeRegion
from ecobenefits.views import tree_benefits, within_itree_regions
from ecobenefits import species_codes_for_regions


class EcoTest(UrlTestCase):
    def setUp(self):

        self.instance = make_instance(is_public=True)

        self.user = make_commander_user(self.instance)

        self.species = Species(otm_code='CEAT',
                               genus='cedrus',
                               species='atlantica',
                               max_dbh=2000,
                               max_height=100,
                               instance=self.instance)
        self.species.save_with_user(self.user)

        ITreeRegion.objects.all().delete()

        p1 = Point(-8515941.0, 4953519.0)

        self.region_buffer_in_meters = 1000

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
            '/%s/eco/benefit/tree/%s/' % (self.instance.url_name,
                                          self.tree.id))

    def test_tree_benefit_url_invalid(self):
        self.assert_404(
            '/%s/eco/benefit/tree/999/' % self.instance.url_name)

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
        self.plot.geom.x += self.region_buffer_in_meters * 2
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


class WithinITreeRegionsTest(UrlTestCase):

    def assertViewPerformsCorrectly(self, before_add_expected_value,
                                    after_add_expected_value,
                                    x=-8515941.0,
                                    y=4953519.0,
                                    params=None,
                                    make_point_from_x_y=True):

        params = params or {'x': str(x), 'y': str(y)}
        p = Point(x, y) if make_point_from_x_y else Point(0, 0)

        request = RequestFactory().get('', params)

        result = within_itree_regions(request)
        self.assertEqual(result, before_add_expected_value)

        ITreeRegion.objects.create(code='NoEastXXX',
                                   geometry=MultiPolygon([p.buffer(1000)]))

        result = within_itree_regions(request)
        self.assertEqual(result, after_add_expected_value)

    def test_within_itree_regions_valid(self):
        self.assertViewPerformsCorrectly(before_add_expected_value=False,
                                         after_add_expected_value=True)

    def test_within_itree_regions_no_overlap(self):
        self.assertViewPerformsCorrectly(before_add_expected_value=False,
                                         after_add_expected_value=False,
                                         make_point_from_x_y=False)

    def test_within_itree_regions_no_x(self):
        y = 4953519.0
        self.assertViewPerformsCorrectly(before_add_expected_value=False,
                                         after_add_expected_value=False,
                                         y=y,
                                         params={'y': str(y)})

    def test_within_itree_regions_no_y(self):
        x = -8515941.0
        self.assertViewPerformsCorrectly(before_add_expected_value=False,
                                         after_add_expected_value=False,
                                         x=x,
                                         params={'x': str(x)})

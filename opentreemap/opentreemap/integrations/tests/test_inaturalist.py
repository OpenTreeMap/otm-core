from django.contrib.gis.geos import Point
from mock import patch

from opentreemap.integrations import inaturalist
from opentreemap.integrations.tests import fixtures
from treemap.models import MapFeature, INaturalistObservation, Tree, Plot
from treemap.tests.base import OTMTestCase
from treemap.tests import (make_instance, make_commander_user)


class TestINaturalist(OTMTestCase):
    instance = None
    commander_user = None

    GET_O9N_TARGET = 'opentreemap.integrations.inaturalist.get_o9n'

    def setUp(self):
        self.instance = make_instance()
        self.commander_user = make_commander_user(self.instance)

    def _create_observation(self, o9n_id=32189837, is_identified=False):
        plot = Plot(geom=Point(0, 0), instance=self.instance)
        plot.save_with_user(self.commander_user)

        tree = Tree(instance=self.instance, plot=plot)
        tree.save_with_user(self.commander_user)

        o = INaturalistObservation(is_identified=is_identified,
                                   observation_id=o9n_id,
                                   map_feature=plot,
                                   tree=tree)
        o.save()
        return o

    def test_no_observations(self):
        self.assertEqual(INaturalistObservation.objects.filter(is_identified=False).count(), 0)

        with patch(TestINaturalist.GET_O9N_TARGET) as get_o9n_mock:
            inaturalist.sync_identifications()

        get_o9n_mock.assert_not_called()
        self.assertEqual(INaturalistObservation.objects.filter(is_identified=False).count(), 0)

    def test_identified(self):
        self._create_observation(is_identified=True)

        self.assertEqual(INaturalistObservation.objects.filter(is_identified=False).count(), 0)

        with patch(TestINaturalist.GET_O9N_TARGET) as get_o9n_mock:
            inaturalist.sync_identifications()

        get_o9n_mock.assert_not_called()
        self.assertEqual(INaturalistObservation.objects.filter(is_identified=False).count(), 0)

    def test_unidentified(self):
        o9n_id = 1

        self._create_observation(o9n_id)

        self.assertEqual(INaturalistObservation.objects.filter(is_identified=False).count(), 1)

        with patch(TestINaturalist.GET_O9N_TARGET,
                   return_value=fixtures.get_inaturalist_o9n(o9n_id)) as get_o9n_mock:
            inaturalist.sync_identifications()

        get_o9n_mock.assert_called_once_with(o9n_id)
        self.assertEqual(INaturalistObservation.objects.filter(is_identified=False).count(), 0)


class TestINaturalistPost(OTMTestCase):
    """
    A set of test cases for writing to iNaturalist

    Uncomment these and fill in blanks for actual testing

    TODO make mock testing better
    """

    def test_set_observation_to_captive(self):
        # pick an observation at random for this
        token = inaturalist.get_inaturalist_auth_token()
        observation_id = 51288919

        inaturalist.set_observation_to_captive(token, observation_id)

    def test_get_all_observations(self):
        data = inaturalist.get_all_observations()

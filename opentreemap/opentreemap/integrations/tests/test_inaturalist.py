from django.contrib.gis.geos import Point

from opentreemap.integrations import inaturalist
from treemap.models import MapFeature, INaturalistObservation, Tree, Plot
from treemap.tests.base import OTMTestCase
from treemap.tests import (make_instance, make_commander_user)


class TestINaturalist(OTMTestCase):

    def setUp(self):
        self.instance = make_instance()
        self.commander_user = make_commander_user(self.instance)

    def _createObservation(self, is_identified=False):
        plot = Plot(geom=Point(0, 0), instance=self.instance)
        plot.save_with_user(self.commander_user)

        tree = Tree(instance=self.instance, plot=plot)
        tree.save_with_user(self.commander_user)

        o = INaturalistObservation(is_identified=is_identified,
                                   observation_id=1,
                                   map_feature=plot,
                                   tree=tree)
        o.save()
        return o

    def test_no_observations(self):
        inaturalist.sync_identifications()

    def test_identified(self):
        self._createObservation(is_identified=True)
        inaturalist.sync_identifications()

    def test_unidentified(self):
        self._createObservation()
        inaturalist.sync_identifications()




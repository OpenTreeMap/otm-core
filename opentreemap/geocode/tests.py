from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from treemap.tests.base import OTMTestCase

from geocode.views import geocode
from django.test.client import RequestFactory
from django.http import HttpResponse

from json import loads


class MockGeocodeRequest():
    def __init__(self, address):
        self.REQUEST = {'address': address}


class GeocodeTest(OTMTestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_azavea_office_geocodes_correctly(self):
        res = geocode(MockGeocodeRequest('340 n 12th st philadelphia'))

        self.assertNotIn('error', res,
                         'The response should not have an error property')
        self.assertIn('candidates', res,
                      'The reponse should have a "candidates" property')
        self.assertTrue(len(res['candidates']) > 0,
                        'There should be one or more candidates')

        first_candidate = res['candidates'][0]

        for prop in ['x', 'y', 'srid', 'score']:
            self.assertIn(prop, first_candidate,
                          'Candidates should include "%s"' % prop)

        self.assertEqual(3857, first_candidate['srid'],
                         'The default response srid should be '
                         'spherical mercator')

        self.assertTrue(abs(first_candidate['x'] - (-8366592.924405822)) < 1,
                        'The actual x coordinate was more than 1 meter '
                        'away from the expected value')
        self.assertTrue(abs(first_candidate['y'] - 4859953.672488515) < 1,
                        'The actual y coordinate was more than 1 meter '
                        'away from the expected value')

    def test_geocoding_gibberish_returns_404(self):
        res = geocode(MockGeocodeRequest('n0 w@y th1s will g30code'))

        self.assertTrue(isinstance(res, HttpResponse),
                        'View should return HttpResponse on 404')
        self.assertEqual(404, res.status_code,
                         'Status code should be 404 Not Found')

        response_json = loads(res.content)
        self.assertIn('error', response_json,
                      'The response body should have an "error" property')

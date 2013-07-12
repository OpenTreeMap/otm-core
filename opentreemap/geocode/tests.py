from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.test import TestCase

from geocode.views import geocode
from django.test.client import RequestFactory

import json


class GeocodeTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_simple_address(self):
        addr = "300%20N%2012th%20St%20Philadelphia%20PA"
        req = self.factory.get('/geocode?address=%s' %
                               addr)

        response = geocode(req)

        self.assertEqual(response.status_code, 200)
        rslt = json.loads(response.content)

        x = rslt['x']
        y = rslt['y']

        tgty = 39.957688
        tgtx = -75.158653

        self.assertTrue(abs(x - tgtx) < 0.00001)
        self.assertTrue(abs(y - tgty) < 0.00001)

# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
import copy

from manage_treemap.views.fields import set_search_config
from treemap.tests import make_instance, make_request
from treemap.tests.base import OTMTestCase
from treemap.search_fields import DEFAULT_SEARCH_FIELDS


class SearchConfigTest(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()

    def _set_search(self, **config):
        json_updates = json.dumps({'search_config': config,
                                   'mobile_search_fields': {}})
        request = make_request(method='PUT', body=json_updates)
        set_search_config(request, self.instance)

    def test_setting_search_field_does_not_affect_defaults(self):
        current_default = copy.deepcopy(DEFAULT_SEARCH_FIELDS)
        self._set_search(missing=[{'identifier': 'species.id'}])
        self.assertEqual(current_default, DEFAULT_SEARCH_FIELDS)
        self.assertIn('missing', self.instance.search_config)
        self.assertEqual(self.instance.search_config['missing'],
                         [{'identifier': 'species.id'}])

    def test_setting_search_field_does_not_affect_general(self):
        self._set_search(missing=[{'identifier': 'tree.diameter'}])
        self.assertIn('missing', self.instance.search_config)
        self.assertEqual(self.instance.search_config['missing'],
                         [{'identifier': 'tree.diameter'}])

        self.assertIn('general', self.instance.search_config)
        self.assertEqual(self.instance.search_config['general'],
                         DEFAULT_SEARCH_FIELDS['general'])

# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from treemap.lib.udf import udf_create
from treemap.tests.test_udfs import UdfCRUTestCase


class UdfGenericCreateTest(UdfCRUTestCase):
    def test_non_treemap_model(self):
        self.instance.map_feature_types += ['Bioswale']
        self.instance.save()

        body = {'udf.name': 'Testing choice',
                'udf.model': 'Bioswale',
                'udf.type': 'string'}

        udf_create(body, self.instance)

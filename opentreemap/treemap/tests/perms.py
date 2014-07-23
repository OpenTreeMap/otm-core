# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from treemap.models import Role
from treemap.lib import perms

from treemap.tests.base import OTMTestCase


class PermTestCase(OTMTestCase):
    def test_none_perm(self):
        self.assertEqual(False,
                         perms._allows_perm(Role(),
                                            'NonExistentModel',
                                            any, 'allows_reads'))

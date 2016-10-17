# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from treemap.instance import Instance
from treemap.models import Role, Plot
from treemap.lib import perms
from treemap.tests import make_instance

from treemap.tests.base import OTMTestCase


class PermTestCase(OTMTestCase):
    def test_none_perm(self):
        self.assertEqual(False,
                         perms._allows_perm(Role(),
                                            'NonExistentModel',
                                            any, 'allows_reads'))


class InstancePermissionsTestCase(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.role_yes = self._make_empty_role('yes')
        self.role_no = self._make_empty_role('no')

    def _make_empty_role(self, name):
        return Role.objects.create(
            name=name, instance=self.instance, rep_thresh=0,
            default_permission_level=0)

    def _add_new_permission(self, role, Model, name):
        content_type = ContentType.objects.get_for_model(Model)
        perm = Permission.objects.create(codename=name, name=name,
                                         content_type=content_type)
        role.instance_permissions.add(perm)

    def _add_builtin_permission(self, role, Model, codename):
        content_type = ContentType.objects.get_for_model(Model)
        perm = Permission.objects.get(content_type=content_type,
                                      codename=codename)
        role.instance_permissions.add(perm)

    def test_builtin_permission(self):
        self._add_builtin_permission(self.role_yes, Plot, 'add_plot')
        self.assertTrue(self.role_yes.has_permission('add_plot', Plot))
        self.assertFalse(self.role_no.has_permission('add_plot', Plot))

    def test_new_permission(self):
        self._add_new_permission(self.role_yes, Instance, 'can_fly')
        self.assertTrue(self.role_yes.has_permission('can_fly', Instance))
        self.assertFalse(self.role_no.has_permission('can_fly', Instance))

    def test_lookup_without_model(self):
        self._add_new_permission(self.role_yes, Instance, 'can_fly')
        self.assertTrue(self.role_yes.has_permission('can_fly'))
        self.assertFalse(self.role_no.has_permission('can_fly'))

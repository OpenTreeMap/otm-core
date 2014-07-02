# -*- coding: utf-8 -*-
import json

from django.test import TestCase
from django.test.utils import override_settings

from treemap.audit import FieldPermission
from treemap.lib.object_caches import (clear_caches, role_permissions,
                                       permissions, udf_defs)
from treemap.models import InstanceUser
from treemap.tests import (make_instance, make_commander_user,
                           make_user)
from treemap.udf import UserDefinedFieldDefinition

WRITE = FieldPermission.WRITE_DIRECTLY
READ = FieldPermission.READ_ONLY


@override_settings(USE_OBJECT_CACHES=True)
class PermissionsCacheTest(TestCase):
    def setUp(self):
        clear_caches()
        self.instance = make_instance()
        self.user = make_commander_user(self.instance)
        self.role = self.user.get_role(self.instance)

        self.simple_user = make_user()
        default_role = self.instance.default_role
        FieldPermission(model_name='Plot', field_name='geom',
                        role=default_role, instance=self.instance,
                        permission_level=READ).save()

    def get_permission(self, perms, field_name, expectedCount):
        perms = [p for p in perms if p.field_name == field_name]
        self.assertEqual(len(perms), expectedCount)
        return perms[0] if expectedCount == 1 else None

    def get_role_permission(self, role, expectedCount, model_name='Plot',
                            field_name='geom'):
        perms = role_permissions(role, self.instance, model_name)
        return self.get_permission(perms, field_name, expectedCount)

    def get_user_permission(self, user, expectedCount, model_name='Plot',
                            field_name='geom'):
        perms = permissions(user, self.instance, model_name)
        return self.get_permission(perms, field_name, expectedCount)

    def assert_role_permission(self, role, level, model_name='Plot',
                               field_name='geom'):
        perm = self.get_role_permission(role, 1, model_name, field_name)
        self.assertEqual(level, perm.permission_level)

    def assert_user_permission(self, user, level, model_name='Plot',
                               field_name='geom'):
        perm = self.get_user_permission(user, 1, model_name, field_name)
        self.assertEqual(level, perm.permission_level)

    def set_permission(self, role, level, model_name='Plot',
                       field_name='geom'):
        fp, created = FieldPermission.objects.get_or_create(
            model_name=model_name,
            field_name=field_name,
            role=role,
            instance=self.instance)
        fp.permission_level = level
        fp.save()

    def get_single_perm_qs(self, role, model_name='Plot', field_name='geom'):
        return FieldPermission.objects.filter(
            model_name=model_name,
            field_name=field_name,
            role=role,
            instance=self.instance
        )

    def set_permission_silently(self, role, level, model_name='Plot',
                                field_name='geom'):
        # update() sends no signals, so cache won't be invalidated
        qs = self.get_single_perm_qs(role, model_name, field_name)
        qs.update(permission_level=level)

    def delete_permission(self, role, model_name='Plot', field_name='geom'):
        qs = self.get_single_perm_qs(role, model_name, field_name)
        qs.delete()

    def test_user_permission(self):
        self.assert_user_permission(self.user, WRITE)

    def test_role_permission(self):
        self.assert_role_permission(self.role, WRITE)

    def test_default_role(self):
        self.assert_user_permission(self.simple_user, READ)

    def test_empty_user(self):
        self.assert_user_permission(None, READ)

    def test_empty_model_name(self):
        perms = permissions(self.user, self.instance)
        self.assertEqual(len(perms), 80)

    def test_unknown_model_name(self):
        self.get_user_permission(self.user, 0, 'foo')
        self.get_role_permission(self.user, 0, 'foo')

    def test_unknown_field_name(self):
        self.get_user_permission(self.user, 0, 'Plot', 'bar')
        self.get_role_permission(self.role, 0, 'Plot', 'bar')

    def test_user_perm_sees_perm_update(self):
        self.assert_user_permission(self.user, WRITE)  # loads cache
        self.set_permission(self.role, READ)
        self.assert_user_permission(self.user, READ)

    def test_role_perm_sees_perm_update(self):
        self.assert_user_permission(self.user, WRITE)  # loads cache
        self.set_permission(self.role, READ)
        self.assert_role_permission(self.role, READ)

    def test_user_perm_sees_perm_delete(self):
        self.assert_user_permission(self.user, WRITE)  # loads cache
        self.delete_permission(self.role)
        self.get_user_permission(self.user, 0)

    def test_user_perm_sees_role_update(self):
        iuser = InstanceUser.objects.get(user=self.user)
        iuser.role = self.instance.default_role
        iuser.save_with_user(self.user)
        self.assert_user_permission(self.user, READ)

    def test_user_perm_sees_external_update(self):
        self.assert_user_permission(self.user, WRITE)  # loads cache
        # Simulate external update by setting permission without
        # invalidating the cache, then updating the instance timestamp
        self.set_permission_silently(self.role, READ)
        self.assert_user_permission(self.user, WRITE)
        self.instance.adjuncts_timestamp += 1
        self.instance.save()
        self.assert_user_permission(self.user, READ)

    def test_role_perm_sees_external_update(self):
        self.assert_user_permission(self.user, WRITE)  # loads cache
        # Simulate external update by setting permission without
        # invalidating the cache, then updating the instance timestamp
        self.set_permission_silently(self.role, READ)
        self.assert_role_permission(self.role, WRITE)
        self.instance.adjuncts_timestamp += 1
        self.instance.save()
        self.assert_role_permission(self.role, READ)


@override_settings(USE_OBJECT_CACHES=True)
class UDFDefinitionCacheTest(TestCase):
    def setUp(self):
        clear_caches()
        self.instance = make_instance()
        self.udfd_plot_a = self.make_udf_def('Plot', 'a')
        self.udfd_plot_b = self.make_udf_def('Plot', 'b')
        self.udfd_tree_a = self.make_udf_def('Tree', 'a')

    def make_udf_def(self, model_type, name):
        return UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type=model_type,
            datatype=json.dumps({'type': 'string'}),
            iscollection=False,
            name=name)

    def assert_udf_def_count(self, model_name, count):
        defs = udf_defs(self.instance, model_name)
        self.assertEqual(len(defs), count)

    def assert_udf_name(self, model_name, name):
        defs = udf_defs(self.instance, model_name)
        self.assertEqual(len(defs), 1)
        self.assertEqual(defs[0].name, name)

    def test_defs_cached(self):
        self.assert_udf_def_count('Plot', 2)
        self.assert_udf_def_count('Tree', 1)

    def test_invalid_model_name(self):
        self.assert_udf_def_count('foo', 0)

    def test_update(self):
        self.assert_udf_name('Tree', 'a')  # load cache
        self.udfd_tree_a.name = 'c'
        self.udfd_tree_a.save()
        self.assert_udf_name('Tree', 'c')

    def test_delete(self):
        self.assert_udf_name('Tree', 'a')  # load cache
        UserDefinedFieldDefinition.objects \
            .filter(model_type='Tree') \
            .delete()
        self.assert_udf_def_count('Tree', 0)

    def test_external_update(self):
        self.assert_udf_name('Tree', 'a')  # load cache
        # Simulate external update by setting permission without
        # invalidating the cache, then updating the instance timestamp.
        # update() sends no signals, so cache won't be invalidated.
        UserDefinedFieldDefinition.objects \
            .filter(model_type='Tree') \
            .update(name='c')
        self.assert_udf_name('Tree', 'a')
        self.instance.adjuncts_timestamp += 1
        self.instance.save()
        self.assert_udf_name('Tree', 'c')

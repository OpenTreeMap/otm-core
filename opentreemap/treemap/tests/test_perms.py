# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import Point

from treemap.audit import AuthorizeException
from treemap.instance import Instance
from treemap.models import Role, Plot, Tree
from treemap.models import TreePhoto
from treemap.lib import perms
from treemap.tests import (make_instance, make_user, make_tweaker_role,
                           make_commander_user, LocalMediaTestCase)


class PermissionsTestCase(LocalMediaTestCase):
    def setUp(self):
        super(PermissionsTestCase, self).setUp()

        self.p = Point(-8515941.0, 4953519.0)

        self.instance = make_instance(point=self.p)
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


class PermsTest(PermissionsTestCase):
    def setUp(self):
        super(PermsTest, self).setUp()
        self.role_no = make_tweaker_role(self.instance, 'no')

    def test_none_perm(self):
        self.assertEqual(False,
                         perms._allows_perm(Role(),
                                            'NonExistentModel',
                                            any, 'allows_reads'))

    def test_plot_is_creatable(self):
        self._add_builtin_permission(self.role_yes, Plot, 'add_plot')
        self.assertTrue(perms.plot_is_creatable(self.role_yes))

    def test_plot_is_deletable(self):
        self._add_builtin_permission(self.role_yes, Plot, 'delete_plot')

        user_yes = make_user(instance=self.instance,
                             make_role=lambda inst: self.role_yes)
        plot = Plot(instance=self.instance)

        self.assertTrue(
            perms.is_deletable(user_yes.get_instance_user(self.instance),
                               plot))

    def test_plot_is_not_creatable(self):
        self.assertFalse(perms.plot_is_creatable(self.role_no))

    def test_plot_is_not_deletable(self):
        user_no = make_user(instance=self.instance,
                            make_role=lambda inst: self.role_no)
        plot = Plot(instance=self.instance)

        self.assertFalse(
            perms.is_deletable(user_no.get_instance_user(self.instance),
                               plot))

    def test_tree_photo_is_addable(self):
        self._add_builtin_permission(self.role_yes, TreePhoto, 'add_treephoto')
        plot = Plot(instance=self.instance)
        self.assertTrue(perms.photo_is_addable(self.role_yes, plot))

    def test_tree_photo_is_not_addable(self):
        self._add_builtin_permission(self.role_no, Tree, 'add_tree')
        self._add_builtin_permission(self.role_no, Plot, 'add_plot')
        plot = Plot(instance=self.instance)
        self.assertFalse(perms.photo_is_addable(self.role_no, plot))

    def test_user_can_create_tree_photo(self):
        self._add_builtin_permission(self.role_yes, TreePhoto, 'add_treephoto')
        commander = make_commander_user(self.instance)
        plot = Plot(instance=self.instance, geom=self.p)
        plot.save_with_user(commander)
        tree = Tree(plot=plot, instance=self.instance)
        tree.save_with_user(commander)
        user_yes = make_user(instance=self.instance,
                             make_role=lambda inst: self.role_yes)
        photo = TreePhoto(instance=self.instance,
                          map_feature=plot, tree=tree)
        photo.set_image(self.load_resource('tree1.gif'))
        self.assertTrue(photo.user_can_create(user_yes))

    def test_user_cannot_create_tree_photo(self):
        self._add_builtin_permission(self.role_no, Tree, 'add_tree')
        self._add_builtin_permission(self.role_no, Plot, 'add_plot')
        commander = make_commander_user(self.instance)
        plot = Plot(instance=self.instance, geom=self.p)
        plot.save_with_user(commander)
        tree = Tree(plot=plot, instance=self.instance)
        tree.save_with_user(commander)
        user_no = make_user(instance=self.instance,
                            make_role=lambda inst: self.role_no)
        photo = TreePhoto(instance=self.instance,
                          map_feature=plot, tree=tree)
        photo.set_image(self.load_resource('tree1.gif'))
        self.assertFalse(photo.user_can_create(user_no))

    def test_tree_photo_is_deletable(self):
        commander = make_commander_user(self.instance)
        plot = Plot(instance=self.instance, geom=self.p)
        plot.save_with_user(commander)
        tree = Tree(plot=plot, instance=self.instance)
        tree.save_with_user(commander)
        image = self.load_resource('tree1.gif')

        photo = tree.add_photo(image, commander)

        self._add_builtin_permission(self.role_yes, TreePhoto,
                                     'delete_treephoto')
        user_yes = make_user(instance=self.instance,
                             make_role=lambda inst: self.role_yes)
        self.assertTrue(
            perms.is_deletable(user_yes.get_instance_user(self.instance),
                               photo))

    def test_tree_photo_is_not_deletable(self):
        commander = make_commander_user(self.instance)
        plot = Plot(instance=self.instance, geom=self.p)
        plot.save_with_user(commander)
        tree = Tree(plot=plot, instance=self.instance)
        tree.save_with_user(commander)
        image = self.load_resource('tree1.gif')

        photo = tree.add_photo(image, commander)

        user_no = make_user(instance=self.instance,
                            make_role=lambda inst: self.role_no)
        self.assertFalse(
            perms.is_deletable(user_no.get_instance_user(self.instance),
                               photo))

    def test_user_can_delete_tree_photo(self):
        commander = make_commander_user(self.instance)
        plot = Plot(instance=self.instance, geom=self.p)
        plot.save_with_user(commander)
        tree = Tree(plot=plot, instance=self.instance)
        tree.save_with_user(commander)
        image = self.load_resource('tree1.gif')

        photo = tree.add_photo(image, commander)

        self._add_builtin_permission(self.role_yes, TreePhoto,
                                     'delete_treephoto')
        user_yes = make_user(instance=self.instance,
                             make_role=lambda inst: self.role_yes)
        self.assertTrue(photo.user_can_delete(user_yes))

    def test_user_cannot_delete_tree_photo(self):
        commander = make_commander_user(self.instance)
        plot = Plot(instance=self.instance, geom=self.p)
        plot.save_with_user(commander)
        tree = Tree(plot=plot, instance=self.instance)
        tree.save_with_user(commander)
        image = self.load_resource('tree1.gif')

        photo = tree.add_photo(image, commander)

        user_no = make_user(instance=self.instance,
                            make_role=lambda inst: self.role_no)
        self.assertFalse(photo.user_can_delete(user_no))


class InstancePermissionsTest(PermissionsTestCase):
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


class WritableTest(PermissionsTestCase):
    def test_plot_is_writable_if_can_create_tree(self):
        self.commander_user = make_commander_user(self.instance)
        self.commander_role = \
            self.commander_user.get_instance_user(self.instance).role
        self.tree_only_user = make_user(self.instance)
        self.tree_only_role = self.instance.default_role

        content_type = ContentType.objects.get_for_model(Tree)
        add_tree_perm = Permission.objects.get(content_type=content_type,
                                               codename='add_tree')
        self.tree_only_role.instance_permissions.add(add_tree_perm)
        self.tree_only_role.save()

        self.p = Point(-8515941.0, 4953519.0)
        self.plot = Plot(instance=self.instance, width=12, geom=self.p)
        self.plot.save_with_user(self.commander_user)

        plot2 = Plot(instance=self.instance, width=12, geom=self.p)
        self.assertRaises(AuthorizeException,
                          plot2.save_with_user,
                          self.tree_only_user)

        self.tree = Tree(instance=self.instance, plot=self.plot)
        self.tree.save_with_user(self.tree_only_user)

        self.assertTrue(self.tree.user_can_create(self.tree_only_user))

        # The plot should be writable if the user can create a tree
        self.assertTrue(perms.map_feature_is_writable(
            self.tree_only_role,
            self.plot))

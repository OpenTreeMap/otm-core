from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import itertools
import datetime

from django.db.models import Q
from django.utils.tree import Node

from django.test import TestCase
from django.test.client import RequestFactory
from treemap.models import (Tree, Instance, Plot, User, Species, Role,
                            FieldPermission, Boundary, InstanceSpecies,
                            ImportEvent)

from treemap.audit import (Audit, UserTrackingException, AuthorizeException,
                           ReputationMetric)

from treemap.views import (audits, boundary_to_geojson, boundary_autocomplete,
                           _execute_filter, species_list)

from django.contrib.gis.geos import Point, MultiPolygon, Polygon
from django.core.exceptions import FieldError

from django.contrib.gis.measure import Distance

from audit import approve_or_reject_audit_and_apply

import search
import json

######################################
## SETUP FUNCTIONS
######################################

def make_simple_boundary(name, n=1):
    b = Boundary()
    b.geom = MultiPolygon(make_simple_polygon(n))
    b.name = name
    b.category = "Unknown"
    b.sort_order = 1
    b.save()
    return b


def make_simple_polygon(n=1):
    """
    Creates a simple, point-like polygon for testing distances
    so it will save to the geom field on a Boundary.

    The idea is to create small polygons such that the n-value
    that is passed in can identify how far the polygon will be
    from the origin.

    For example:
    p1 = make_simple_polygon(1)
    p2 = make_simple_polygon(2)

    p1 will be closer to the origin.
    """
    return Polygon(((n, n), (n, n + 1), (n + 1, n + 1), (n, n)))


def _make_loaded_role(instance, name, rep_thresh, permissions):
    role, created = Role.objects.get_or_create(
        name=name, instance=instance, rep_thresh=rep_thresh)

    role.save()

    for perm in permissions:
        model_name, field_name, permission_level = perm
        FieldPermission.objects.get_or_create(
            model_name=model_name, field_name=field_name,
            permission_level=permission_level, role=role,
            instance=instance)

    return role


def make_commander_role(instance):
    permissions = (
        ('Plot', 'geom', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'width', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'length', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'address_street', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'address_city', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'address_zip', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'import_event', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'owner_orig_id', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'readonly', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'plot', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'species', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'import_event', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'readonly', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'diameter', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'height', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'canopy_height', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'date_planted', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'date_removed', FieldPermission.WRITE_DIRECTLY))
    return _make_loaded_role(instance, 'commander', 3, permissions)


def make_officer_role(instance):
    permissions = (
        ('Plot', 'geom', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'length', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'readonly', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'diameter', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'plot', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'height', FieldPermission.WRITE_DIRECTLY))
    return _make_loaded_role(instance, 'officer', 3, permissions)


def make_apprentice_role(instance):
    permissions = (
        ('Plot', 'geom', FieldPermission.WRITE_WITH_AUDIT),
        ('Plot', 'width', FieldPermission.WRITE_WITH_AUDIT),
        ('Plot', 'length', FieldPermission.WRITE_WITH_AUDIT),
        ('Plot', 'address_street', FieldPermission.WRITE_WITH_AUDIT),
        ('Plot', 'address_city', FieldPermission.WRITE_WITH_AUDIT),
        ('Plot', 'address_zip', FieldPermission.WRITE_WITH_AUDIT),
        ('Plot', 'import_event', FieldPermission.WRITE_WITH_AUDIT),
        ('Plot', 'owner_orig_id', FieldPermission.WRITE_WITH_AUDIT),
        ('Plot', 'readonly', FieldPermission.WRITE_WITH_AUDIT),
        ('Tree', 'plot', FieldPermission.WRITE_WITH_AUDIT),
        ('Tree', 'species', FieldPermission.WRITE_WITH_AUDIT),
        ('Tree', 'import_event', FieldPermission.WRITE_WITH_AUDIT),
        ('Tree', 'readonly', FieldPermission.WRITE_WITH_AUDIT),
        ('Tree', 'diameter', FieldPermission.WRITE_WITH_AUDIT),
        ('Tree', 'height', FieldPermission.WRITE_WITH_AUDIT),
        ('Tree', 'canopy_height', FieldPermission.WRITE_WITH_AUDIT),
        ('Tree', 'date_planted', FieldPermission.WRITE_WITH_AUDIT),
        ('Tree', 'date_removed', FieldPermission.WRITE_WITH_AUDIT))
    return _make_loaded_role(instance, 'apprentice', 2, permissions)


def make_observer_role(instance):
    permissions = (
        ('Plot', 'geom', FieldPermission.READ_ONLY),
        ('Plot', 'length', FieldPermission.READ_ONLY),
        ('Tree', 'diameter', FieldPermission.READ_ONLY),
        ('Tree', 'height', FieldPermission.READ_ONLY))
    return _make_loaded_role(instance, 'observer', 2, permissions)


def make_instance(name='i1'):
    global_role, _ = Role.objects.get_or_create(name='global', rep_thresh=0)

    p1 = Point(0, 0)

    instance, _ = Instance.objects.get_or_create(
        name=name, geo_rev=0, center=p1, default_role=global_role)

    return instance


def make_system_user():
    try:
        system_user = User.objects.get(username="system_user")
    except Exception:
        system_user = User(username="system_user")
        system_user.save_base()
    return system_user


def make_basic_user(instance, username):
    """ A helper function for making an instance and user

    You'll still want to load the permissions you need for each
    test onto the user's role. """
    system_user = make_system_user()

    user = User(username=username)
    user.save_with_user(system_user)
    return user


def make_instance_and_basic_user():
    instance = make_instance()
    basic_user = make_basic_user(instance, "custom_user")
    return instance, basic_user


def make_instance_and_system_user():
    instance = make_instance()
    system_user = make_system_user()
    return instance, system_user


######################################
## Custom test classes
######################################


class ViewTestCase(TestCase):
    def _make_request(self, params={}):
        return self.factory.get("hello/world", params)

    def setUp(self):
        self.factory = RequestFactory()
        self.instance = make_instance()

    def call_view(self, view, view_args=[], view_keyword_args={},
                  url="hello/world", url_args={}):
        request = self.factory.get(url, url_args)
        response = view(request, *view_args, **view_keyword_args)
        return json.loads(response.content)

    def call_instance_view(self, view, view_args=None, view_keyword_args={},
                           url="hello/world", url_args={}):
        if (view_args is None):
            view_args = [self.instance.pk]
        else:
            view_args.insert(0, self.instance.pk)

        return self.call_view(view, view_args, view_keyword_args,
                              url, url_args)


######################################
## TESTS
######################################

class HashModelTest(TestCase):
    def setUp(self):
        self.instance, self.user = make_instance_and_basic_user()
        permissions = (
            ('Plot', 'geom', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'width', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'length', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'address_street', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'plot', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'readonly', FieldPermission.WRITE_DIRECTLY))

        self.user.roles.add(
            _make_loaded_role(self.instance, "custom", 0, permissions))

        self.p1 = Point(-8515941.0, 4953519.0)
        self.p2 = Point(-7615441.0, 5953519.0)

    def test_changing_fields_changes_hash(self):
        plot = Plot(geom=self.p1, instance=self.instance, created_by=self.user)
        plot.save_with_user(self.user)

        #
        # Make sure regular field updates change the hash
        #
        h1 = plot.hash
        plot.width = 44
        plot.save_with_user(self.user)
        h2 = plot.hash

        self.assertNotEqual(h1, h2, "Hashes should change")

        h1 = plot.hash
        plot.address_street = "test"
        plot.save_with_user(self.user)
        h2 = plot.hash

        self.assertNotEqual(h1, h2, "Hashes should change")

        #
        # Verify adding a new tree updates the plot hash
        #

        h1 = plot.hash
        tree = Tree(plot=plot,
                    instance=self.instance,
                    readonly=False,
                    created_by=self.user)
        tree.save_with_user(self.user)
        h2 = plot.hash

        self.assertNotEqual(h1, h2, "Hashes should change")

        #
        # Verify that updating a tree related to a plot also
        # changes the plot hash
        #

        h1 = plot.hash
        tree.readonly = True
        tree.save_with_user(self.user)

        h2 = plot.hash

        self.assertNotEqual(h1, h2, "Hashes should change")


class GeoRevIncr(TestCase):
    def setUp(self):
        self.p1 = Point(-8515941.0, 4953519.0)
        self.p2 = Point(-7615441.0, 5953519.0)
        self.instance, self.user = make_instance_and_basic_user()

        permissions = (
            ('Plot', 'geom', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'width', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'length', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'address_street', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'address_city', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'address_zip', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'import_event', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'owner_orig_id', FieldPermission.WRITE_DIRECTLY),
            ('Plot', 'readonly', FieldPermission.WRITE_DIRECTLY))

        self.user.roles.add(
            _make_loaded_role(self.instance, "custom", 0, permissions))

    def hash_and_rev(self):
        i = Instance.objects.get(pk=self.instance.pk)
        return [i.geo_rev_hash, i.geo_rev]

    def test_changing_geometry_updates_counter(self):
        rev1h, rev1 = self.hash_and_rev()

        # Create
        plot1 = Plot(geom=self.p1, instance=self.instance,
                     created_by=self.user)

        plot1.save_with_user(self.user)

        rev2h, rev2 = self.hash_and_rev()

        self.assertNotEqual(rev1h, rev2h)
        self.assertEqual(rev1 + 1, rev2)

        plot2 = Plot(geom=self.p2, instance=self.instance,
                     created_by=self.user)

        plot2.save_with_user(self.user)

        rev3h, rev3 = self.hash_and_rev()

        self.assertNotEqual(rev2h, rev3h)
        self.assertEqual(rev2 + 1, rev3)

        # Update
        plot2.geom = self.p1
        plot2.save_with_user(self.user)

        rev4h, rev4 = self.hash_and_rev()

        self.assertNotEqual(rev3h, rev4h)
        self.assertEqual(rev3 + 1, rev4)

        # Delete
        plot2.delete_with_user(self.user)

        rev5h, rev5 = self.hash_and_rev()

        self.assertNotEqual(rev4h, rev5h)
        self.assertEqual(rev4 + 1, rev5)


class UserRoleFieldPermissionTest(TestCase):
    def setUp(self):
        self.p1 = Point(-8515941.0, 4953519.0)
        self.instance, system_user = make_instance_and_system_user()

        self.outlaw_role = Role(name='outlaw', instance=self.instance,
                                rep_thresh=1)

        self.outlaw_role.save()

        self.commander = User(username="commander")
        self.commander.save_with_user(system_user)
        self.commander.roles.add(make_commander_role(self.instance))

        self.officer = User(username="officer")
        self.officer.save_with_user(system_user)
        self.officer.roles.add(make_officer_role(self.instance))

        self.observer = User(username="observer")
        self.observer.save_with_user(system_user)
        self.observer.roles.add(make_observer_role(self.instance))

        self.outlaw = User(username="outlaw")
        self.outlaw.save_with_user(system_user)
        self.outlaw.roles.add(self.outlaw_role)

        self.anonymous = User(username="")
        self.anonymous.save_with_user(system_user)

        self.plot = Plot(geom=self.p1, instance=self.instance,
                         created_by=self.officer)

        self.plot.save_with_user(self.officer)

        self.tree = Tree(plot=self.plot, instance=self.instance,
                         created_by=self.officer)

        self.tree.save_with_user(self.officer)

    def test_no_permission_cant_edit_object(self):
        self.plot.length = 10
        self.assertRaises(AuthorizeException,
                          self.plot.save_with_user, self.outlaw)

        self.assertNotEqual(Plot.objects.get(pk=self.plot.pk).length, 10)

        self.tree.diameter = 10
        self.assertRaises(AuthorizeException,
                          self.tree.save_with_user, self.outlaw)

        self.assertNotEqual(Tree.objects.get(pk=self.tree.pk).diameter, 10)

    def test_readonly_cant_edit_object(self):
        self.plot.length = 10
        self.assertRaises(AuthorizeException,
                          self.plot.save_with_user, self.observer)

        self.assertNotEqual(Plot.objects.get(pk=self.plot.pk).length, 10)

        self.tree.diameter = 10
        self.assertRaises(AuthorizeException,
                          self.tree.save_with_user, self.observer)

        self.assertNotEqual(Tree.objects.get(pk=self.tree.pk).diameter, 10)

    def test_writeperm_allows_write(self):
        self.plot.length = 10
        self.plot.save_with_user(self.officer)
        self.assertEqual(Plot.objects.get(pk=self.plot.pk).length, 10)

        self.tree.diameter = 10
        self.tree.save_with_user(self.officer)
        self.assertEqual(Tree.objects.get(pk=self.tree.pk).diameter, 10)

    def test_save_new_object_authorized(self):
        '''Save two new objects with authorized user, nothing should happen'''
        plot = Plot(geom=self.p1, instance=self.instance,
                    created_by=self.officer)

        plot.save_with_user(self.officer)

        tree = Tree(plot=plot, instance=self.instance,
                    created_by=self.officer)

        tree.save_with_user(self.officer)

    def test_save_new_object_unauthorized(self):
        plot = Plot(geom=self.p1, instance=self.instance,
                    created_by=self.outlaw)

        self.assertRaises(AuthorizeException,
                          plot.save_with_user, self.outlaw)

        tree = Tree(plot=plot, instance=self.instance,
                    created_by=self.outlaw)

        self.assertRaises(AuthorizeException,
                          tree.save_with_user, self.outlaw)

    def test_delete_object(self):
        self.assertRaises(AuthorizeException,
                          self.tree.delete_with_user, self.outlaw)

        self.assertRaises(AuthorizeException,
                          self.plot.delete_with_user, self.outlaw)

        self.assertRaises(AuthorizeException,
                          self.tree.delete_with_user, self.officer)

        self.assertRaises(AuthorizeException,
                          self.plot.delete_with_user, self.officer)

        self.tree.delete_with_user(self.commander)
        self.plot.delete_with_user(self.commander)

    def test_clobbering_authorized(self):
        "When clobbering with a superuser, nothing should happen"
        self.plot.width = 5
        self.plot.save_with_user(self.commander)

        plot = Plot.objects.get(pk=self.plot.pk)
        plot.clobber_unauthorized(self.commander)
        self.assertEqual(self.plot.width, plot.width)

    def test_clobbering_unauthorized(self):
        "Clobbering changes an unauthorized field to None"
        self.plot.width = 5
        self.plot.save_base()

        plot = Plot.objects.get(pk=self.plot.pk)
        plot.clobber_unauthorized(self.observer)
        self.assertEqual(None, plot.width)

        plot = Plot.objects.get(pk=self.plot.pk)
        plot.clobber_unauthorized(self.outlaw)
        self.assertEqual(None, plot.width)

    def test_clobbering_whole_queryset(self):
        "Clobbering also works on entire querysets"
        self.plot.width = 5
        self.plot.save_base()

        plots = Plot.objects.filter(pk=self.plot.pk)
        plot = Plot.clobber_queryset(plots, self.observer)[0]
        self.assertEqual(None, plot.width)

    def test_write_fails_if_any_fields_cant_be_written(self):
        """ If a user tries to modify several fields simultaneously,
        only some of which s/he has access to, the write will fail
        for all fields."""
        self.plot.length = 10
        self.plot.width = 110

        self.assertRaises(AuthorizeException,
                          self.plot.save_with_user, self.officer)

        self.assertNotEqual(Plot.objects.get(pk=self.plot.pk).length, 10)
        self.assertNotEqual(Plot.objects.get(pk=self.plot.pk).width, 110)

        self.tree.diameter = 10
        self.tree.canopy_height = 110

        self.assertRaises(AuthorizeException, self.tree.save_with_user,
                          self.officer)

        self.assertNotEqual(Tree.objects.get(pk=self.tree.pk).diameter,
                            10)

        self.assertNotEqual(Tree.objects.get(pk=self.tree.pk).canopy_height,
                            110)


class InstanceValidationTest(TestCase):

    def setUp(self):

        global_role = Role(name='global', rep_thresh=0)
        global_role.save()

        p = Point(-8515941.0, 4953519.0)
        self.instance1 = Instance(name='i1', geo_rev=0, center=p,
                                  default_role=global_role)

        self.instance1.save()

        self.instance2 = Instance(name='i2', geo_rev=0, center=p,
                                  default_role=global_role)

        self.instance2.save()

    def test_invalid_instance_returns_404(self):
        response = self.client.get('/%s/' % self.instance1.pk)
        self.assertEqual(response.status_code, 200)

        response = self.client.get('/1000/')
        self.assertEqual(response.status_code, 404)


class ScopeModelTest(TestCase):

    def setUp(self):
        p1 = Point(-8515222.0, 4953200.0)
        p2 = Point(-7515222.0, 3953200.0)

        self.instance1, self.user = make_instance_and_basic_user()
        self.global_role = self.instance1.default_role

        self.instance2 = Instance(name='i2', geo_rev=1, center=p2,
                                  default_role=self.global_role)
        self.instance2.save()

        for i in [self.instance1, self.instance2]:
            FieldPermission(model_name='Plot', field_name='geom',
                            permission_level=FieldPermission.WRITE_DIRECTLY,
                            role=self.global_role,
                            instance=i).save()
            FieldPermission(model_name='Tree', field_name='plot',
                            permission_level=FieldPermission.WRITE_DIRECTLY,
                            role=self.global_role,
                            instance=i).save()

        self.plot1 = Plot(geom=p1, instance=self.instance1,
                          created_by=self.user)

        self.plot1.save_with_user(self.user)

        self.plot2 = Plot(geom=p2, instance=self.instance2,
                          created_by=self.user)

        self.plot2.save_with_user(self.user)

        tree_combos = itertools.product(
            [self.plot1, self.plot2],
            [self.instance1, self.instance2],
            [True, False],
            [self.user])

        for tc in tree_combos:
            plot, instance, readonly, created_by = tc
            t = Tree(plot=plot, instance=instance, readonly=readonly,
                     created_by=created_by)

            t.save_with_user(self.user)

    def test_scope_model_method(self):
        all_trees = Tree.objects.all()
        orm_instance_1_trees = list(all_trees.filter(instance=self.instance1))
        orm_instance_2_trees = list(all_trees.filter(instance=self.instance2))

        method_instance_1_trees = list(self.instance1.scope_model(Tree))
        method_instance_2_trees = list(self.instance2.scope_model(Tree))

        # Test that it returns the same as using the ORM
        self.assertEquals(orm_instance_1_trees, method_instance_1_trees)
        self.assertEquals(orm_instance_2_trees, method_instance_2_trees)

        # Test that it didn't grab all trees
        self.assertNotEquals(list(all_trees), method_instance_1_trees)
        self.assertNotEquals(list(all_trees), method_instance_2_trees)

        self.assertRaises(FieldError,
                          (lambda: self.instance1.scope_model(Species)))


class AuditTest(TestCase):

    def setUp(self):

        self.instance = make_instance()
        self.user1 = make_basic_user(self.instance, 'charles')
        self.user2 = make_basic_user(self.instance, 'amy')

        permissions = (
            ('Plot', 'geom', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'plot', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'species', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'import_event', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'readonly', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'diameter', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'height', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'canopy_height', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'date_planted', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'date_removed', FieldPermission.WRITE_DIRECTLY))

        self.user1.roles.add(_make_loaded_role(self.instance,
                                               "custom1", 3, permissions))

        self.user2.roles.add(_make_loaded_role(self.instance,
                                               "custom2", 3, permissions))

    def assertAuditsEqual(self, exps, acts):
        self.assertEqual(len(exps), len(acts))

        exps = list(exps)
        for act in acts:
            act = act.dict()
            act['created'] = None

            if act in exps:
                exps.remove(act)
            else:
                raise AssertionError('Missing audit record for %s' % act)

    def make_audit(self, pk, field, old, new,
                   action=Audit.Type.Insert, user=None, model=u'Tree'):
        if field:
            field = unicode(field)
        if old:
            old = unicode(old)
        if new:
            new = unicode(new)

        user = user or self.user1

        return {'model': model,
                'model_id': pk,
                'instance_id': self.instance.pk,
                'field': field,
                'previous_value': old,
                'current_value': new,
                'user_id': user.pk,
                'action': action,
                'requires_auth': False,
                'ref_id': None,
                'created': None}

    def test_cant_use_regular_methods(self):
        p = Point(-8515222.0, 4953200.0)
        plot = Plot(geom=p, instance=self.instance, created_by=self.user1)
        self.assertRaises(UserTrackingException, plot.save)
        self.assertRaises(UserTrackingException, plot.delete)

        tree = Tree()
        self.assertRaises(UserTrackingException, tree.save)
        self.assertRaises(UserTrackingException, tree.delete)

    def test_basic_audit(self):
        p = Point(-8515222.0, 4953200.0)
        plot = Plot(geom=p, instance=self.instance, created_by=self.user1)
        plot.save_with_user(self.user1)

        self.assertAuditsEqual([
            self.make_audit(plot.pk, 'id', None, str(plot.pk), model='Plot'),
            self.make_audit(plot.pk, 'instance', None, plot.instance.pk,
                            model='Plot'),
            self.make_audit(plot.pk, 'readonly', None, 'False',
                            model='Plot'),
            self.make_audit(plot.pk, 'geom', None, str(plot.geom),
                            model='Plot'),
            self.make_audit(plot.pk, 'created_by', None, self.user1.pk,
                            model='Plot')], plot.audits())

        t = Tree(plot=plot, instance=self.instance, readonly=True,
                 created_by=self.user1)

        t.save_with_user(self.user1)

        expected_audits = [
            self.make_audit(t.pk, 'id', None, str(t.pk)),
            self.make_audit(t.pk, 'instance', None, t.instance.pk),
            self.make_audit(t.pk, 'readonly', None, True),
            self.make_audit(t.pk, 'created_by', None, self.user1.pk),
            self.make_audit(t.pk, 'plot', None, plot.pk)]

        self.assertAuditsEqual(expected_audits, t.audits())

        t.readonly = False
        t.save_with_user(self.user2)

        expected_audits.insert(
            0, self.make_audit(t.pk, 'readonly', 'True', 'False',
                               action=Audit.Type.Update, user=self.user2))

        self.assertAuditsEqual(expected_audits, t.audits())

        old_pk = t.pk
        t.delete_with_user(self.user1)

        expected_audits.insert(
            0, self.make_audit(old_pk, None, None, None,
                               action=Audit.Type.Delete, user=self.user1))

        self.assertAuditsEqual(
            expected_audits,
            Audit.audits_for_model('Tree', self.instance, old_pk))


class PendingTest(TestCase):
    def setUp(self):
        self.instance = make_instance()
        self.system_user = make_system_user()
        self.system_user.roles.add(make_commander_role(self.instance))

        self.direct_user = make_basic_user(self.instance, "user write direct")
        self.direct_user.roles.add(make_officer_role(self.instance))

        self.pending_user = make_basic_user(self.instance, "user pdg")
        self.pending_user.roles.add(make_apprentice_role(self.instance))

        self.observer_user = make_basic_user(self.instance, "user obs")
        self.observer_user.roles.add(make_observer_role(self.instance))

        self.p1 = Point(-7615441.0, 5953519.0)
        self.plot = Plot(geom=self.p1, instance=self.instance,
                         created_by=self.system_user)
        self.plot.save_with_user(self.direct_user)

    def test_reject(self):
        # Setup
        readonly_orig = self.plot.readonly
        readonly_new = not readonly_orig

        self.plot.readonly = readonly_new
        self.plot.save_with_user(self.pending_user)

        # Generated a single audit
        audit = Audit.objects.filter(requires_auth=True)[0]

        # Should match the model
        self.assertTrue(audit.requires_auth)
        self.assertEqual(audit.model_id, self.plot.pk)

        # Users who don't have direct field access can't reject
        # the edit
        self.assertRaises(AuthorizeException,
                          approve_or_reject_audit_and_apply,
                          audit, self.observer_user, approved=False)

        # User with write access can reject the change
        approve_or_reject_audit_and_apply(
            audit, self.direct_user, approved=False)

        # Reload from DB
        audit = Audit.objects.get(pk=audit.pk)

        # Audit should be marked as processed
        self.assertIsNotNone(audit.ref_id)

        # Ref'd audit should note rejection
        refaudit = Audit.objects.get(pk=audit.ref_id.pk)
        self.assertEqual(refaudit.user, self.direct_user)
        self.assertEqual(refaudit.action, Audit.Type.PendingReject)

        # The object shouldn't have changed
        self.assertEqual(Plot.objects.get(pk=self.plot.pk).readonly,
                         readonly_orig)

        ohash = Plot.objects.get(pk=self.plot.pk).hash

        # Can't reject a pending edit twice
        self.assertRaises(Exception,
                          approve_or_reject_audit_and_apply,
                          audit, self.direct_user, approved=False)

        # Can't approve a pending edit once rejected
        self.assertRaises(Exception,
                          approve_or_reject_audit_and_apply,
                          audit, self.direct_user, approved=False)

        # Nothing was changed, no audits were added
        self.assertEqual(ohash,
                         Plot.objects.get(pk=self.plot.pk).hash)

    def test_accept(self):
        # Setup
        readonly_orig = self.plot.readonly
        readonly_new = not readonly_orig

        self.plot.readonly = readonly_new
        self.plot.save_with_user(self.pending_user)

        # Generated a single audit
        audit = Audit.objects.filter(requires_auth=True)[0]

        # Should match the model
        self.assertTrue(audit.requires_auth)
        self.assertEqual(audit.model_id, self.plot.pk)

        # Users who don't have direct field access can't accept
        # the edit
        self.assertRaises(AuthorizeException,
                          approve_or_reject_audit_and_apply,
                          audit, self.observer_user, approved=True)

        # User with write access can apply the change
        approve_or_reject_audit_and_apply(
            audit, self.direct_user, approved=True)

        # Reload from DB
        audit = Audit.objects.get(pk=audit.pk)

        # Audit should be marked as processed
        self.assertIsNotNone(audit.ref_id)

        # Ref'd audit should note approval
        refaudit = Audit.objects.get(pk=audit.ref_id.pk)
        self.assertEqual(refaudit.user, self.direct_user)
        self.assertEqual(refaudit.action, Audit.Type.PendingApprove)

        # The object should be updated
        self.assertEqual(Plot.objects.get(pk=self.plot.pk).readonly,
                         readonly_new)

        ohash = Plot.objects.get(pk=self.plot.pk).hash

        # Can't approve a pending edit twice
        self.assertRaises(Exception,
                          approve_or_reject_audit_and_apply,
                          audit, self.direct_user, approved=True)

        # Can't reject a pending edit once approved
        self.assertRaises(Exception,
                          approve_or_reject_audit_and_apply,
                          audit, self.direct_user, approved=False)

        # Nothing was changed, no audits were added
        self.assertEqual(ohash,
                         Plot.objects.get(pk=self.plot.pk).hash)


class ReputationTest(TestCase):
    def setUp(self):
        self.instance = make_instance()

        self.system_user = make_system_user()
        self.system_user.roles.add(make_commander_role(self.instance))

        self.privileged_user = make_basic_user(self.instance, "user1")
        self.privileged_user.roles.add(make_officer_role(self.instance))

        self.unprivileged_user = make_basic_user(self.instance, "user2")
        self.unprivileged_user.roles.add(make_apprentice_role(self.instance))

        self.p1 = Point(-7615441.0, 5953519.0)
        self.plot = Plot(geom=self.p1, instance=self.instance,
                         created_by=self.system_user)

        self.plot.save_with_user(self.system_user)

        rm = ReputationMetric(instance=self.instance, model_name='Tree',
                              action=Audit.Type.Insert, direct_write_score=2,
                              approval_score=20, denial_score=5)
        rm.save()

    def test_reputations_increase_for_direct_writes(self):
        self.assertEqual(self.privileged_user.reputation, 0)
        t = Tree(plot=self.plot, instance=self.instance,
                 readonly=True, created_by=self.privileged_user)
        t.save_with_user(self.privileged_user)
        self.assertGreater(self.privileged_user.reputation, 0)


class BoundaryViewTest(ViewTestCase):


    def setUp(self):
        super(BoundaryViewTest, self).setUp()

        self.test_boundaries = [
            'alabama',
            'arkansas',
            'far',
            'farquaad\'s castle',
            'farther',
            'farthest',
            'ferenginar',
            'romulan star empire',
        ]
        self.test_boundary_hashes = []
        for i, v in enumerate(self.test_boundaries):
            boundary = make_simple_boundary(v, i)
            self.instance.boundaries.add(boundary)
            self.instance.save()
            self.test_boundary_hashes.append({'name': boundary.name,
                                              'category': boundary.category})

    def test_boundary_to_geojson_view(self):
        boundary = make_simple_boundary("Hello, World", 1)
        response = boundary_to_geojson(
            self._make_request(),
            boundary.pk)

        self.assertEqual(response.content, boundary.geom.geojson)

    def test_autocomplete_view(self):
        response = boundary_autocomplete(
            self._make_request({'q': 'fa'}),
            self.instance)

        self.assertEqual(response, self.test_boundary_hashes[2:6])

    def test_autocomplete_view_scoped(self):
        # make a boundary that is not tied to this
        # instance, should not be in the search
        # results
        make_simple_boundary("fargo", 1)
        response = boundary_autocomplete(
            self._make_request({'q': 'fa'}),
            self.instance)

        self.assertEqual(response, self.test_boundary_hashes[2:6])

    def test_autocomplete_view_limit(self):
        response = boundary_autocomplete(
            self._make_request({'q': 'fa',
                                'max_items': 2}),
            self.instance)

        self.assertEqual(response, self.test_boundary_hashes[2:4])


class RecentEditsViewTest(TestCase):
    def setUp(self):
        self.instance = make_instance()

        self.system_user = make_system_user()
        self.system_user.roles.add(make_commander_role(self.instance))

        self.officer = User(username="officer")
        self.officer.save_with_user(self.system_user)
        self.officer.roles.add(make_officer_role(self.instance))

        self.pending_user = make_basic_user(self.instance, "user pdg")
        self.pending_user.roles.add(make_apprentice_role(self.instance))

        self.p1 = Point(-7615441.0, 5953519.0)
        self.factory = RequestFactory()

        self.plot = Plot(geom=self.p1, instance=self.instance,
                         created_by=self.system_user)

        self.plot.save_with_user(self.system_user)

        self.tree = Tree(plot=self.plot, instance=self.instance,
                         created_by=self.officer)

        self.tree.save_with_user(self.officer)

        self.tree.diameter = 4
        self.tree.save_with_user(self.officer)

        self.tree.diameter = 5
        self.tree.save_with_user(self.officer)

        self.plot.width = 9
        self.plot.save_with_user(self.system_user)

        self.plot_delta = {
            "model": "Plot",
            "model_id": self.plot.pk,
            "ref_id": None,
            "action": Audit.Type.Update,
            "previous_value": None,
            "current_value": "9",
            "requires_auth": False,
            "user_id": self.system_user.pk,
            "instance_id": self.instance.pk,
            "field": "width"
        }

        self.next_plot_delta = self.plot_delta.copy()
        self.next_plot_delta["current_value"] = "44"
        self.next_plot_delta["previous_value"] = "9"

        self.plot.width = 44
        self.plot.save_with_user(self.system_user)

    def check_audits(self, url, dicts):
        req = self.factory.get(url)
        resulting_audits = [a.audit.dict()
                            for a
                            in audits(req, self.instance)['audits']]

        self.assertEqual(len(dicts), len(resulting_audits))

        for expected, generated in zip(dicts, resulting_audits):
            for k, v in expected.iteritems():
                self.assertEqual(v, generated[k])

    def test_multiple_deltas(self):
        self.check_audits('/blah/?page_size=2',
                          [self.next_plot_delta, self.plot_delta])

    def test_paging(self):
        self.check_audits('/blah/?page_size=1&page=1', [self.plot_delta])

    def test_model_filtering_errors(self):
        self.assertRaises(Exception,
                          self.check_audits,
                          "/blah/?model_id=%s&page=0&page_size=1" %
                          self.tree.pk, [])

        self.assertRaises(Exception,
                          self.check_audits,
                          "/blah/?model_id=%s&"
                          "models=Tree,Plot&page=0&page_size=1" %
                          self.tree.pk, [])

        self.assertRaises(Exception,
                          self.check_audits,
                          "/blah/?models=User&page=0&page_size=1", [])

    def test_model_filtering(self):

        specific_tree_delta = {
            "model": "Tree",
            "model_id": self.tree.pk,
            "action": Audit.Type.Update,
            "user_id": self.officer.pk,
        }

        generic_tree_delta = {
            "model": "Tree"
        }

        generic_plot_delta = {
            "model": "Plot"
        }

        self.check_audits(
            "/blah/?model_id=%s&models=Tree&page=0&page_size=1" % self.tree.pk,
            [specific_tree_delta])

        self.check_audits(
            "/blah/?model_id=%s&models=Plot&page=0&page_size=1" % self.plot.pk,
            [self.next_plot_delta])

        self.check_audits(
            "/blah/?models=Plot,Tree&page=0&page_size=3",
            [generic_plot_delta, generic_plot_delta, generic_tree_delta])

        self.check_audits(
            "/blah/?models=Plot&page=0&page_size=5",
            [generic_plot_delta] * 5)

        self.check_audits(
            "/blah/?models=Tree&page=0&page_size=5",
            [generic_tree_delta] * 5)

    def test_user_filtering(self):

        generic_officer_delta = {
            "user_id": self.officer.pk
        }

        generic_systemuser_delta = {
            "user_id": self.system_user.pk
        }

        self.check_audits(
            "/blah/?user=%s&page_size=3" % self.officer.pk,
            [generic_officer_delta] * 3)

        self.check_audits(
            "/blah/?user=%s&page_size=3" % self.system_user.pk,
            [generic_systemuser_delta] * 3)

    def test_pending_filtering(self):
        self.plot.width = 22
        self.plot.save_with_user(self.pending_user)

        pending_plot_delta = {
            "model": "Plot",
            "model_id": self.plot.pk,
            "ref_id": None,
            "action": Audit.Type.Update,
            "previous_value": "44",
            "current_value": "22",
            "requires_auth": True,
            "user_id": self.pending_user.pk,
            "instance_id": self.instance.pk,
            "field": "width"
        }

        approve_delta = {
            "action": Audit.Type.PendingApprove,
            "user_id": self.system_user.pk,
            "instance_id": self.instance.pk,
        }

        self.check_audits(
            "/blah/?page_size=2&include_pending=true",
            [pending_plot_delta, self.next_plot_delta])

        self.check_audits(
            "/blah/?page_size=2&include_pending=false",
            [self.next_plot_delta, self.plot_delta])

        a = approve_or_reject_audit_and_apply(
            Audit.objects.all().order_by("-created")[0],
            self.system_user, approved=True)

        pending_plot_delta["ref_id"] = a.pk

        self.check_audits(
            "/blah/?page_size=4&include_pending=false",
            [approve_delta, pending_plot_delta,
             self.next_plot_delta, self.plot_delta])


class FilterParserTests(TestCase):
    def destructure_query_set(self, node):
        """
        Django query objects are not comparable by themselves, but they
        are built from a tree (django.util.tree) and stored in nodes

        This function generates a canonical representation using sets and
        tuples of a query tree

        This can be used to verify that query structures are made correctly
        """
        if isinstance(node, Node):
            n = (node.connector,
                 frozenset(
                     {self.destructure_query_set(c) for c in node.children}))

            if node.negated:
                n = ('NOT', n)

            return n
        else:
            return node

    def test_key_parser_plots(self):
        # Plots go directly to a field
        match = search._parse_predicate_key('plot.width')
        self.assertEqual(match, 'width')

    def test_key_parser_trees(self):
        # Trees require a prefix and the field
        match = search._parse_predicate_key('tree.dbh')
        self.assertEqual(match, 'tree__dbh')

    def test_key_parser_invalid_model(self):
        # Invalid models should raise an exception
        self.assertRaises(search.ParseException,
                          search._parse_predicate_key,
                          "user.id")

    def test_key_parser_too_many_dots(self):
        # Dotted fields are also not allowed
        self.assertRaises(search.ParseException,
                          search._parse_predicate_key,
                          "plot.width.other")

    def test_combinator_and(self):
        qa = Q(a=1)
        qb = Q(b=1)
        qc = Q(c=1)

        # Simple AND
        ands = search._apply_combinator('AND', [qa, qb, qc])

        self.assertEqual(self.destructure_query_set(ands),
                         self.destructure_query_set(qa & qb & qc))

    def test_combinator_or(self):
        qa = Q(a=1)
        qb = Q(b=1)
        qc = Q(c=1)

        # Simple OR
        ands = search._apply_combinator('OR', [qa, qb, qc])

        self.assertEqual(self.destructure_query_set(ands),
                         self.destructure_query_set(qa | qb | qc))

    def test_combinator_invalid_combinator(self):
        qa = Q(a=1)
        qb = Q(b=1)
        qc = Q(c=1)

        # Error if not AND,OR
        self.assertRaises(search.ParseException,
                          search._apply_combinator,
                          'ANDarg', [qa, qb])

        self.assertRaises(search.ParseException,
                          search._apply_combinator,
                          qc, [qa, qb])

    def test_combinator_invalid_empty(self):
        # Error if empty
        self.assertRaises(search.ParseException,
                          search._apply_combinator,
                          'AND', [])

    def test_boundary_constraint(self):
        b = Boundary.objects.create(
            geom=MultiPolygon(make_simple_polygon(0)),
            name='whatever',
            category='whatever',
            sort_order=1)

        inparams = search._parse_dict_value({'IN_BOUNDARY': b.pk})
        self.assertEqual(inparams,
                         {'__contained': b.geom})

    def test_constraints_in(self):
        inparams = search._parse_dict_value({'IN': [1, 2, 3]})
        self.assertEqual(inparams,
                         {'__in': [1, 2, 3]})

    def test_constraints_is(self):
        # "IS" is a special case in that we don't need to appl
        # a suffix at all
        isparams = search._parse_dict_value({'IS': 'what'})
        self.assertEqual(isparams,
                         {'': 'what'})

    def test_constraints_invalid_groups(self):
        # It is an error to combine mutually exclusive groups
        self.assertRaises(search.ParseException,
                          search._parse_dict_value,
                          {'IS': 'what', 'IN': [1, 2, 3]})

        self.assertRaises(search.ParseException,
                          search._parse_dict_value,
                          {'IS': 'what', 'MIN': 3})

    def test_constraints_invalid_keys(self):
        self.assertRaises(search.ParseException,
                          search._parse_dict_value,
                          {'EXCLUSIVE': 9})

        self.assertRaises(search.ParseException,
                          search._parse_dict_value,
                          {'IS NOT VALID KEY': 'what'})

    def test_contraint_min(self):
        const = search._parse_dict_value({'MIN': 5})
        self.assertEqual(const, {'__gte': 5})

    def test_contraint_max(self):
        const = search._parse_dict_value({'MAX': 5})
        self.assertEqual(const, {'__lte': 5})

    def test_contraint_max_with_exclusive(self):
        const = search._parse_dict_value(
            {'MAX': {'VALUE': 5,
                     'EXCLUSIVE': True}})
        self.assertEqual(const, {'__lt': 5})

        const = search._parse_dict_value(
            {'MAX': {'VALUE': 5,
                     'EXCLUSIVE': False}})
        self.assertEqual(const, {'__lte': 5})

    def test_constraints_min_and_max(self):
        const = search._parse_dict_value(
            {'MIN': 5,
             'MAX': {'VALUE': 9,
                     'EXCLUSIVE': False}})
        self.assertEqual(const, {'__lte': 9, '__gte': 5})

    def test_within_radius(self):
        const = search._parse_dict_value(
            {'WITHIN_RADIUS': {
                "RADIUS": 5,
                "POINT": {
                    "x": 100,
                    "y": 50}}})
        self.assertEqual(const,
                         {'__dwithin': (Point(100, 50), Distance(m=5))})

    def test_parse_species_predicate(self):
        pred = search._parse_predicate(
            {'species.id': 113,
             'species.flowering': True})

        target = ('AND', {('tree__species__id', 113),
                          ('tree__species__flowering', True)})

        self.assertEqual(self.destructure_query_set(pred), target)

    def test_parse_predicate(self):
        pred = search._parse_predicate(
            {'plot.width':
             {'MIN': 5,
              'MAX': {'VALUE': 9,
                      'EXCLUSIVE': False}},
             'tree.height':
             9})

        p1 = ('AND', {('width__lte', 9),
                      ('width__gte', 5),
                      ('tree__height', 9)})

        self.assertEqual(self.destructure_query_set(pred),
                         p1)

        pred = search._parse_predicate(
            {'tree.leaf_type': {'IS': 9},
             'tree.last_updated_by': 4})

        p2 = ('AND', {('tree__leaf_type', 9),
                      ('tree__last_updated_by', 4)})

        self.assertEqual(self.destructure_query_set(pred),
                         p2)

    def test_parse_filter_no_wrapper(self):
        pred = search._parse_filter(
            {'plot.width':
             {'MIN': 5,
              'MAX': {'VALUE': 9,
                      'EXCLUSIVE': False}},
             'tree.height': 9})

        p = ('AND',
             {('width__lte', 9),
              ('width__gte', 5),
              ('tree__height', 9)})

        self.assertEqual(self.destructure_query_set(pred), p)

    def test_parse_filter_and(self):
        pred = search._parse_filter(
            ['AND',
             {'plot.width':
              {'MIN': 5,
               'MAX': {'VALUE': 9,
                       'EXCLUSIVE': False}},
              'tree.height': 9},
             {'tree.leaf_type': {'IS': 9},
              'tree.last_updated_by': 4}])

        p = ('AND',
             {('width__lte', 9),
              ('width__gte', 5),
              ('tree__height', 9),
              ('tree__leaf_type', 9),
              ('tree__last_updated_by', 4)})

        self.assertEqual(self.destructure_query_set(pred), p)

    def test_parse_filter_or(self):
        pred = search._parse_filter(
            ['OR',
             {'plot.width':
              {'MIN': 5,
               'MAX': {'VALUE': 9,
                       'EXCLUSIVE': False}},
              'tree.height': 9},
             {'tree.leaf_type': {'IS': 9},
              'tree.last_updated_by': 4}])

        p1 = ('AND', frozenset({('width__lte', 9),
                                ('width__gte', 5),
                                ('tree__height', 9)}))

        p2 = ('AND', frozenset({('tree__leaf_type', 9),
                                ('tree__last_updated_by', 4)}))

        self.assertEqual(self.destructure_query_set(pred), ('OR', {p1, p2}))


class SearchTests(TestCase):
    def setUp(self):
        self.instance = make_instance()

        self.system_user = make_system_user()
        self.system_user.roles.add(make_commander_role(self.instance))

        self.p1 = Point(-7615441.0, 5953519.0)

    def create_tree_and_plot(self):
        plot = Plot(geom=self.p1, instance=self.instance,
                    created_by=self.system_user)

        plot.save_with_user(self.system_user)

        tree = Tree(plot=plot, instance=self.instance,
                    created_by=self.system_user)

        tree.save_with_user(self.system_user)

        return plot, tree

    def test_species_id_search(self):
        species1 = Species.objects.create(
            common_name='Species-1',
            genus='Genus-1',
            symbol='S1')

        species2 = Species.objects.create(
            common_name='Species-2',
            genus='Genus-2',
            symbol='S1')

        p1, t1 = self.create_tree_and_plot()
        p2, t2 = self.create_tree_and_plot()
        p3, t3 = self.create_tree_and_plot()

        t1.species = species1
        t1.save_with_user(self.system_user)

        t2.species = species2
        t2.save_with_user(self.system_user)

        species1_filter = json.dumps({'species.id': species1.pk})
        species2_filter = json.dumps({'species.id': species2.pk})
        species3_filter = json.dumps({'species.id': -1})

        self.assertEqual(
            {p1.pk},
            {p.pk
             for p in _execute_filter(self.instance, species1_filter)})

        self.assertEqual(
            {p2.pk},
            {p.pk
             for p in _execute_filter(self.instance, species2_filter)})

        self.assertEqual(
            0, len(_execute_filter(self.instance, species3_filter)))

    def test_boundary_search(self):
        # Unit Square
        b1 = Boundary.objects.create(
            geom=MultiPolygon(make_simple_polygon(0)),
            name='whatever',
            category='whatever',
            sort_order=1)

        # Unit Square translated by (0.2,0.2)
        b2 = Boundary.objects.create(
            geom=MultiPolygon(make_simple_polygon(0.2)),
            name='whatever',
            category='whatever',
            sort_order=1)

        # Unit square translated by (-1,-1)
        b3 = Boundary.objects.create(
            geom=MultiPolygon(make_simple_polygon(-1)),
            name='whatever',
            category='whatever',
            sort_order=1)

        plot1 = Plot(geom=Point(0.9, 0.9), instance=self.instance,
                     created_by=self.system_user)
        plot2 = Plot(geom=Point(1.1, 1.1), instance=self.instance,
                     created_by=self.system_user)
        plot3 = Plot(geom=Point(2.5, 2.5), instance=self.instance,
                     created_by=self.system_user)

        for p in (plot1, plot2, plot3):
            p.save_with_user(self.system_user)

        boundary1_filter = json.dumps({'plot.geom':
                                       {'IN_BOUNDARY': b1.pk}})

        self.assertEqual(
            {plot1.pk},
            {p.pk
             for p in _execute_filter(self.instance, boundary1_filter)})

        boundary2_filter = json.dumps({'plot.geom':
                                       {'IN_BOUNDARY': b2.pk}})

        self.assertEqual(
            {plot1.pk, plot2.pk},
            {p.pk
             for p in _execute_filter(self.instance, boundary2_filter)})

        boundary3_filter = json.dumps({'plot.geom':
                                       {'IN_BOUNDARY': b3.pk}})

        self.assertEqual(
            0, len(_execute_filter(self.instance, boundary3_filter)))

    def setup_diameter_test(self):
        p1, t1 = self.create_tree_and_plot()
        t1.diameter = 2.0

        p2, t2 = self.create_tree_and_plot()
        t2.diameter = 4.0

        p3, t3 = self.create_tree_and_plot()
        t3.diameter = 6.0

        p4, t4 = self.create_tree_and_plot()
        t4.diameter = 8.0

        for t in [t1, t2, t3, t4]:
            t.save_with_user(self.system_user)

        return [p1, p2, p3, p4]

    def test_diameter_min_filter(self):
        p1, p2, p3, p4 = self.setup_diameter_test()

        diameter_range_filter = json.dumps({'tree.diameter':
                                            {'MIN': 3.0}})

        ids = {p.pk
               for p
               in _execute_filter(
                   self.instance, diameter_range_filter)}

        self.assertEqual(ids, {p2.pk, p3.pk, p4.pk})

    def test_diameter_max_filter(self):
        p1, p2, p3, p4 = self.setup_diameter_test()

        diameter_range_filter = json.dumps({'tree.diameter':
                                            {'MAX': 3.0}})

        ids = {p.pk
               for p
               in _execute_filter(
                   self.instance, diameter_range_filter)}

        self.assertEqual(ids, {p1.pk})

    def test_within_radius_integration(self):
        test_point = Point(-7615443.0, 5953520.0)
        near_point = Point(-7615444.0, 5953521.0)
        far_point = Point(-9615444.0, 8953521.0)

        near_plot = Plot(geom=near_point, instance=self.instance,
                         created_by=self.system_user)
        near_plot.save_with_user(self.system_user)
        near_tree = Tree(plot=near_plot, instance=self.instance,
                         created_by=self.system_user)
        near_tree.save_with_user(self.system_user)

        # just to make sure that the geospatial
        # query actually filters by distance
        far_plot = Plot(geom=far_point, instance=self.instance,
                        created_by=self.system_user)
        far_plot.save_with_user(self.system_user)
        far_tree = Tree(plot=far_plot, instance=self.instance,
                        created_by=self.system_user)
        far_tree.save_with_user(self.system_user)

        radius_filter = json.dumps(
            {'plot.geom':
             {
                 'WITHIN_RADIUS': {
                     'POINT': {'x': test_point.x, 'y': test_point.y},
                     'RADIUS': 10
                 }
             }})

        ids = {p.pk
               for p
               in _execute_filter(
                   self.instance, radius_filter)}

        self.assertEqual(ids, {near_plot.pk})

    def test_diameter_range_filter(self):
        p1, p2, p3, p4 = self.setup_diameter_test()

        diameter_range_filter = json.dumps({'tree.diameter':
                                            {'MAX': 7.0,
                                             'MIN': 3.0}})

        ids = {p.pk
               for p
               in _execute_filter(
                   self.instance, diameter_range_filter)}

        self.assertEqual(ids, {p2.pk, p3.pk})


class SpeciesViewTests(ViewTestCase):
    def setUp(self):
        super(SpeciesViewTests, self).setUp()

        self.species_dict = [
            {'common_name': 'asian cherry', 'genus': 'cherrificus'},
            {'common_name': 'cherrytree', 'genus': 'cherritius',
             'cultivar_name': 'asian'},
            {'common_name': 'elm', 'genus': 'elmitius'},
            {'common_name': 'oak', 'genus': 'acorn',
             'species': 'oakenitus'},
            {'common_name': 'pine', 'genus': 'piniferus',
             'cultivar_name': 'green'},
            {'common_name': 'thing', 'genus': 'elmitius'},
            {'common_name': 'xmas', 'genus': 'christmas',
             'species': 'tree', 'cultivar_name': 'douglass'},
            {'common_name': 'x-mas tree', 'genus': 'xmas',
             'species': 'tree', 'cultivar_name': 'douglass'},
        ]
        self.species_json = []
        for i, item in enumerate(self.species_dict):
            species = Species(common_name=item.get('common_name'),
                              genus=item.get('genus'),
                              species=item.get('species'),
                              cultivar_name=item.get('cultivar_name'),
                              symbol=str(i))
            species.save()
            self.species_json.append(
                {'id': species.id,
                 'common_name': species.common_name,
                 'scientific_name': species.scientific_name})

    def test_get_species_list(self):
        self.assertEquals(species_list(self._make_request(), None),
                          self.species_json)

    def test_get_species_list_filter_common(self):
        self.assertEquals(
            species_list(self._make_request({'q': 'pine'}), None),
            self.species_json[4:5])

    def test_get_species_list_filter_scientific(self):
        self.assertEquals(
            species_list(self._make_request({'q': 'lmitiu'}), None),
            [self.species_json[2], self.species_json[5]])

    def test_get_species_list_filter_both_names(self):
        self.assertEquals(
            species_list(self._make_request({'q': 'xmas'}), None),
            self.species_json[6:8])

    def test_get_species_list_max_items(self):
        self.assertEquals(
            species_list(self._make_request({'max_items': 3}), None),
            self.species_json[:3])

    def test_get_species_list_no_split_match(self):
        self.assertEquals(
            species_list(self._make_request({'q': 'asian cherry'}), None),
            self.species_json[:1])

    def test_get_species_list_contains(self):
        self.assertEquals(
            species_list(self._make_request({'q': 'cherry'}), None),
            self.species_json[:2])

    def test_get_species_list_out_of_order_matches(self):
        self.assertEquals(
            species_list(self._make_request({'q': 'cherry asian'}), None),
            self.species_json[:2])

    def test_get_species_list_punctuation_split(self):
        self.assertEquals(
            species_list(self._make_request({'q': "asian,cherry'cherritius'"}),
                         None),
            self.species_json[1:2])

    def test_get_species_list_no_match(self):
        self.assertEquals(
            species_list(self._make_request({'q': 'cherry elm'}), None), [])


class SpeciesModelTests(TestCase):
    def test_scientific_name_genus(self):
        s = Species(genus='Ulmus')
        self.assertEquals(s.scientific_name, 'Ulmus')

    def test_scientific_name_genus_species(self):
        s = Species(genus='Ulmus', species='rubra')
        self.assertEquals(s.scientific_name, 'Ulmus rubra')

    def test_scientific_name_genus_cultivar(self):
        s = Species(genus='Ulmus', cultivar_name='Columella')
        self.assertEquals(s.scientific_name, "Ulmus 'Columella'")

    def test_scientific_name_all(self):
        s = Species(genus='Ulmus', species='rubra', cultivar_name='Columella')
        self.assertEquals(s.scientific_name, "Ulmus rubra 'Columella'")
        self.assertEquals(self.species_dict, species_list(None, None))

class ModelUnicodeTests(TestCase):

    def setUp(self):
        self.instance = make_instance(name='Test Instance')

        self.species = Species(common_name='Test Common Name', genus='Test Genus',
                               cultivar_name='Test Cultivar', species='Test Species')
        self.species.save_base()

        self.instance_species = InstanceSpecies(instance=self.instance, species=self.species,
                                           common_name='Test Common Name')
        self.instance_species.save_base()

        self.user = make_system_user()

        self.import_event = ImportEvent(imported_by=self.user)
        self.import_event.save_base()

        self.plot = Plot(geom=Point(0, 0), instance=self.instance,
                         address_street="123 Main Street",
                         created_by=self.user)

        self.plot.save_base()

        self.tree = Tree(plot=self.plot, instance=self.instance, created_by=self.user)
        self.tree.save_base()

        self.boundary = make_simple_boundary("Test Boundary")

        self.role = make_commander_role(self.instance)
        self.role.name = "Test Role"
        self.role.save()

        self.field_permission = FieldPermission(model_name="Tree",
                                           field_name="readonly",
                                           permission_level=FieldPermission.READ_ONLY,
                                           role=self.role,
                                           instance=self.instance)
        self.field_permission.save_base()

        self.audit = Audit(action=Audit.Type.Update,
                      model = "Tree",
                      field = "readonly",
                      model_id = 1,
                      user=self.user,
                      previous_value=True,
                      current_value=False)
        self.audit.save_base()

        self.reputation_metric = ReputationMetric(instance=self.instance,
                                             model_name="Tree",
                                             action="Test Action")
        self.reputation_metric.save_base()

    def test_instance_model(self):
        self.assertEqual(unicode(self.instance), "Test Instance")

    def test_species_model(self):
        self.assertEqual(unicode(self.species), "Test Genus Test Species 'Test Cultivar'")

    def test_instance_species_model(self):
        self.assertEqual(unicode(self.instance_species), 'Test Common Name')

    def test_user_model(self):
        self.assertEqual(unicode(self.user), 'system_user')

    def test_import_event_model(self):
        today = datetime.datetime.today().strftime('%Y-%m-%d')
        self.assertEqual(unicode(self.import_event), 'system_user - %s' % today)

    def test_plot_model(self):
        self.assertEqual(unicode(self.plot), 'X: 0.0, Y: 0.0 - 123 Main Street')

    def test_tree_model(self):
        self.assertEqual(unicode(self.tree),
                         'Created by system_user')

    def test_boundary_model(self):
        self.assertEqual(unicode(self.boundary), 'Test Boundary')

    def test_role_model(self):
        self.assertEqual(unicode(self.role), 'Test Role')

    def test_field_permission_model(self):
        self.assertEqual(unicode(self.field_permission), 'Tree.readonly - Test Role')

    def test_audit_model(self):
        self.assertEqual(unicode(self.audit), 'ID: 3 Tree.readonly (1) True => False')

    def test_reputation_metric_model(self):
        self.assertEqual(unicode(self.reputation_metric), 'Test Instance - Tree - Test Action')

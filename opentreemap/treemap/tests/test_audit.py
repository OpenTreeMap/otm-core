# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import psycopg2
import json
from unittest.case import skip

from django.test.client import RequestFactory
from django.core.exceptions import (FieldError, ValidationError,
                                    ObjectDoesNotExist)
from django.core.urlresolvers import reverse

from django.db import IntegrityError, connection
from django.contrib.gis.geos import Point

from stormwater.models import RainBarrel
from treemap.templatetags.util import audit_detail_link

from treemap.models import (Tree, Plot, FieldPermission, User, InstanceUser,
                            Instance)
from treemap.audit import (Audit, Role, UserTrackingException,
                           AuthorizeException, ReputationMetric,
                           approve_or_reject_audits_and_apply,
                           approve_or_reject_audit_and_apply,
                           approve_or_reject_existing_edit,
                           get_id_sequence_name)
from treemap.udf import UserDefinedFieldDefinition
from treemap.tests import (make_instance, make_user_with_default_role,
                           make_user_and_role, make_commander_user,
                           make_officer_user, make_observer_user,
                           make_apprentice_user, set_write_permissions,
                           make_admin_user, make_tweaker_user,
                           make_conjurer_user, make_commander_role)
from treemap.tests.base import OTMTestCase


class ScopeModelTest(OTMTestCase):
    """
    Tests that the various operations on models are scoped to the
    instance they exist within. In general, ForeignKey relationships
    must either be to objects with the same instance, or objects that
    live outside of instance scoping (like Species).
    """

    def setUp(self):
        self.p1 = Point(0, 0)
        self.p2 = Point(5, 5)

        self.instance1 = make_instance(point=self.p1)
        self.instance1.default_role.instance_permissions.add(
            *Role.model_permissions((Plot, Tree)))

        self.user = make_user_with_default_role(self.instance1, 'auser')
        self.instance1.default_role.instance_permissions.add(
            *Role.model_permissions((Plot, Tree)))

        self.instance2 = make_instance(name='i2')
        self.instance2.save()

        iuser = InstanceUser(instance=self.instance2, user=self.user,
                             role=self.instance1.default_role)
        iuser.save_with_user(self.user)

        self.plot1 = Plot(geom=self.p1, instance=self.instance1)

        self.plot1.save_with_user(self.user)

        self.plot2 = Plot(geom=self.p2, instance=self.instance2)

        self.plot2.save_with_user(self.user)

        tree_combos = [
            (self.plot1, self.instance1, True),
            (self.plot1, self.instance1, False),
            (self.plot2, self.instance2, True),
            (self.plot2, self.instance2, False),
        ]

        for plot, instance, readonly in tree_combos:
            t = Tree(plot=plot, instance=instance, readonly=readonly)

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

        # Models that do not have any relation to Instance should
        # raise an error if you attempt to scope them.
        self.assertRaises(FieldError, self.instance1.scope_model, Instance)

    def test_plot_tree_same_instance(self):
        plot = Plot(geom=self.p1, instance=self.instance2)
        plot.save_with_user(self.user)

        tree = Tree(plot=plot, instance=self.instance1, readonly=False)
        self.assertRaises(ValidationError, tree.save_with_user, self.user)


class AuditTest(OTMTestCase):

    def setUp(self):
        inst = self.instance = make_instance()

        field_permissions = (
            ('Tree', 'species', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'readonly', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'diameter', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'height', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'canopy_height', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'date_planted', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'date_removed', FieldPermission.WRITE_DIRECTLY))

        self.user1 = make_user_and_role(inst, 'charles', 'role1',
                                        field_permissions, (Plot, Tree))
        self.user2 = make_user_and_role(inst, 'amy', 'role2',
                                        field_permissions, (Plot, Tree))

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
                'ref': None,
                'created': None}

    def test_cant_use_regular_methods(self):
        plot = Plot(geom=self.instance.center, instance=self.instance)
        self.assertRaises(UserTrackingException, plot.save)
        self.assertRaises(UserTrackingException, plot.delete)

        tree = Tree()
        self.assertRaises(UserTrackingException, tree.save)
        self.assertRaises(UserTrackingException, tree.delete)

    def test_basic_audit(self):
        plot = Plot(geom=self.instance.center, instance=self.instance)
        plot.save_with_user(self.user1)

        self.assertAuditsEqual([
            self.make_audit(plot.pk, 'id', None, str(plot.pk), model='Plot'),
            self.make_audit(plot.pk, 'readonly', None, 'False',
                            model='Plot'),
            self.make_audit(plot.pk, 'geom', None, str(plot.geom),
                            model='Plot')], plot.audits())

        t = Tree(plot=plot, instance=self.instance, readonly=True)

        t.save_with_user(self.user1)

        expected_audits = [
            self.make_audit(t.pk, 'id', None, str(t.pk)),
            self.make_audit(t.pk, 'readonly', None, True),
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

    def test_get_id_sequence_name(self):
        self.assertEqual(get_id_sequence_name(Tree), 'treemap_tree_id_seq')
        self.assertEqual(get_id_sequence_name(Plot),
                         'treemap_mapfeature_id_seq')


class MultiUserTestCase(OTMTestCase):
    def setUp(self):
        self.p1 = Point(-7615441.0, 5953519.0)
        self.instance = make_instance(point=self.p1)
        self.commander_user = make_commander_user(self.instance)
        self.direct_user = make_officer_user(self.instance)
        self.pending_user = make_apprentice_user(self.instance)
        self.observer_user = make_observer_user(self.instance)
        self.outlaw_user = make_user_with_default_role(self.instance, 'outlaw')
        self.tweaker_user = make_tweaker_user(self.instance)
        self.conjurer_user = make_conjurer_user(self.instance)


class ReviewTest(MultiUserTestCase):
    def setUp(self):
        super(ReviewTest, self).setUp()

        self.plot = Plot(geom=self.p1, instance=self.instance)
        self.plot.save_with_user(self.commander_user)

    def test_simple_approve(self):
        self.plot.width = 444
        self.plot.save_with_user(self.commander_user)

        width_audit = self.plot.audits().order_by('-created')[0]

        # Sanity check
        self.assertEqual(width_audit.field, 'width')

        # Should not have a reference associated with it
        self.assertIsNone(width_audit.ref)

        approve_or_reject_existing_edit(
            width_audit, self.commander_user, approved=True)

        width_audit_reloaded = Audit.objects.get(pk=width_audit.pk)
        self.assertIsNotNone(width_audit_reloaded.ref)

        refd = width_audit_reloaded.ref
        self.assertEqual(refd.action, Audit.Type.ReviewApprove)

    def test_reject_regular_edit(self):
        self.plot.width = 444
        self.plot.save_with_user(self.commander_user)

        self.plot.width = 555
        self.plot.save_with_user(self.commander_user)

        width_audit = self.plot.audits().order_by('-created')[0]

        # Sanity check
        self.assertEqual(width_audit.field, 'width')

        # Should not have a reference associated with it
        self.assertIsNone(width_audit.ref)

        approve_or_reject_existing_edit(
            width_audit, self.commander_user, approved=False)

        width_audit_reloaded = Audit.objects.get(pk=width_audit.pk)
        self.assertIsNotNone(width_audit_reloaded.ref)

        refd = width_audit_reloaded.ref
        self.assertEqual(refd.action, Audit.Type.ReviewReject)

        plot_reloaded = Plot.objects.get(pk=self.plot.pk)
        self.assertEqual(plot_reloaded.width, 444)

    def test_reject_id_edit(self):
        id_audit = self.plot.audits().get(field='id')

        approve_or_reject_existing_edit(
            id_audit, self.commander_user, approved=False)

        all_audits = list(self.plot.audits())

        self.assertNotEqual(len(all_audits), 0)

        updated_audit = Audit.objects.get(pk=id_audit.pk)
        ref_audit = updated_audit.ref

        self.assertIsNotNone(ref_audit)
        self.assertEqual(ref_audit.action, Audit.Type.ReviewReject)

        self.assertRaises(Plot.DoesNotExist,
                          Plot.objects.get, pk=self.plot.pk)

    def test_requires_write_permissions_on_field(self):
        self.plot.width = 333
        self.plot.save_with_user(self.commander_user)

        width_audit = self.plot.audits().order_by('-created')[0]

        # Read only can't edit
        FieldPermission.objects.filter(field_name='width').update(
            permission_level=FieldPermission.READ_ONLY)

        self.assertRaises(AuthorizeException,
                          approve_or_reject_existing_edit,
                          width_audit, self.commander_user, approved=True)

        # Neither can 'write with audit'
        FieldPermission.objects.filter(field_name='width').update(
            permission_level=FieldPermission.WRITE_WITH_AUDIT)

        self.assertRaises(AuthorizeException,
                          approve_or_reject_existing_edit,
                          width_audit, self.commander_user, approved=True)

        # But write directly can
        FieldPermission.objects.filter(field_name='width').update(
            permission_level=FieldPermission.WRITE_DIRECTLY)

        approve_or_reject_existing_edit(
            width_audit, self.commander_user, approved=True)

    def test_reject_or_approve_pending_edit_fails(self):
        FieldPermission.objects.filter(field_name='width').update(
            permission_level=FieldPermission.WRITE_WITH_AUDIT)

        self.plot.width = 333
        self.plot.save_with_user(self.commander_user)

        pdg_width_audit = self.plot.audits().order_by('-created')[0]

        FieldPermission.objects.filter(field_name='width').update(
            permission_level=FieldPermission.WRITE_DIRECTLY)

        self.assertRaises(Exception,
                          approve_or_reject_existing_edit,
                          pdg_width_audit, self.commander_user, approved=True)

    def test_rejecting_old_edits_doesnt_update_object(self):
        self.plot.width = 333
        self.plot.save_with_user(self.commander_user)

        self.plot.width = 444
        self.plot.save_with_user(self.commander_user)

        width_audit = self.plot.audits().order_by('-created')[0]

        self.plot.width = 555
        self.plot.save_with_user(self.commander_user)

        approve_or_reject_existing_edit(
            width_audit, self.commander_user, approved=False)

        reloaded_plot = Plot.objects.get(pk=self.plot.pk)
        self.assertEqual(reloaded_plot.width, 555)

    def test_approving_edits_on_deleted_obj_doesnt_fail(self):
        self.plot.width = 444
        self.plot.save_with_user(self.commander_user)

        width_audit = self.plot.audits().order_by('-created')[0]

        self.plot.delete_with_user(self.commander_user, cascade=True)

        approve_or_reject_existing_edit(
            width_audit, self.commander_user, approved=False)


class PendingTest(OTMTestCase):
    def setUp(self):
        self.p1 = Point(-7615441.0, 5953519.0)
        self.instance = make_instance(point=self.p1)
        self.commander_user = make_commander_user(self.instance)
        self.direct_user = make_officer_user(self.instance)
        self.pending_user = make_apprentice_user(self.instance)
        self.observer_user = make_observer_user(self.instance)

        self.plot = Plot(geom=self.p1, instance=self.instance, length=5.0)
        self.plot.save_with_user(self.commander_user)

    def test_reject(self):
        # Setup
        plot_length_orig = self.plot.length
        plot_length_new = plot_length_orig + 1.0

        self.plot.length = plot_length_new
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
        self.assertIsNotNone(audit.ref)

        # Ref'd audit should note rejection
        refaudit = Audit.objects.get(pk=audit.ref.pk)
        self.assertEqual(refaudit.user, self.direct_user)
        self.assertEqual(refaudit.action, Audit.Type.PendingReject)

        # The object shouldn't have changed
        self.assertEqual(Plot.objects.get(pk=self.plot.pk).length,
                         plot_length_orig)

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
        plot_length_orig = self.plot.length
        plot_length_new = plot_length_orig + 1.0

        self.plot.length = plot_length_new
        self.plot.save_with_user(self.pending_user)

        # Generated a single audit
        audit = Audit.objects.filter(requires_auth=True)[0]

        # Should match the model
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
        self.assertIsNotNone(audit.ref)

        # Ref'd audit should note approval
        refaudit = Audit.objects.get(pk=audit.ref.pk)
        self.assertEqual(refaudit.user, self.direct_user)
        self.assertEqual(refaudit.action, Audit.Type.PendingApprove)

        # The object should be updated
        self.assertEqual(Plot.objects.get(pk=self.plot.pk).length,
                         plot_length_new)

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


class PendingInsertTest(OTMTestCase):

    def setUp(self):
        psycopg2.extras.register_hstore(connection.cursor(), globally=True)

        self.p1 = Point(-7615441.0, 5953519.0)
        self.instance = make_instance(point=self.p1)
        self.commander_user = make_commander_user(self.instance)
        self.pending_user = make_apprentice_user(self.instance)

        # we need there to be no audits so that we can
        # iterate over all audits without conflict
        Audit.objects.all().delete()

    def test_can_create_obj_even_if_some_fields_are_pending(self):
        # Give pending user permissions on all of the required
        # fields for a plot
        role = self.pending_user.get_instance_user(self.instance).role
        role.fieldpermission_set\
            .filter(field_name__in=['id', 'geom', 'readonly'])\
            .update(permission_level=FieldPermission.WRITE_DIRECTLY)

        self.assertEquals(Plot.objects.count(), 0)

        # new_plot should be created, but there should be
        # a pending record for length (and it should not be
        # applied)
        new_plot = Plot(geom=self.p1,
                        instance=self.instance,
                        length=4)

        new_plot.save_with_user(self.pending_user)

        self.assertEquals(Plot.objects.count(), 1)

    @skip("Insert pending approval not implemented at this time")
    def test_insert_writes_when_approved(self):

        new_plot = Plot(geom=self.p1, instance=self.instance)
        new_plot.save_with_user(self.pending_user)

        new_tree = Tree(plot=new_plot, instance=self.instance)
        new_tree.save_with_user(self.pending_user)

        self.assertEquals(Plot.objects.count(), 0)
        self.assertEquals(Tree.objects.count(), 0)

        approve_or_reject_audits_and_apply(
            list(new_tree.audits()) + list(new_plot.audits()),
            self.commander_user, True)

        self.assertEqual(Plot.objects.all().count(), 1)
        self.assertEqual(Tree.objects.all().count(), 1)

    def test_record_is_created_when_nullables_are_still_pending(self):
        new_plot = Plot(geom=self.p1, instance=self.instance)
        new_plot.save_with_user(self.pending_user)

        new_tree = Tree(plot=new_plot, instance=self.instance,
                        diameter=10, height=10, readonly=False)

        new_tree.save_with_user(self.pending_user)

        approve_or_reject_audits_and_apply(
            new_plot.audits(),
            self.commander_user, True)

        insert_audit = Audit.objects.filter(model='Tree')\
                                    .get(field='id')
        field_audits = Audit.objects.filter(model='Tree')\
                                    .filter(field__in=['readonly', 'diameter',
                                                       'plot'])
        for audit in field_audits:
            approve_or_reject_audit_and_apply(
                audit, self.commander_user, approved=True)

        approve_or_reject_audit_and_apply(insert_audit,
                                          self.commander_user, True)

        real_tree = Tree.objects.get(pk=new_tree.pk)

        self.assertEqual(real_tree.plot_id, new_plot.pk)
        self.assertEqual(real_tree.diameter, 10)
        self.assertEqual(real_tree.height, None)
        self.assertNotEqual(real_tree.readonly, True)

    def test_reject_insert_rejects_updates(self):
        new_plot = Plot(geom=self.p1, instance=self.instance)
        new_plot.save_with_user(self.pending_user)

        insert_audit = Audit.objects.filter(model='Plot')\
                                    .get(field='id')
        field_audits = Audit.objects.filter(model='Plot')\
                                    .exclude(field='id')

        for audit in field_audits:
            approve_or_reject_audit_and_apply(
                audit, self.commander_user, approved=True)

        approve_or_reject_audit_and_apply(insert_audit,
                                          self.commander_user, False)

        # need to refresh the field_audits collection from the db
        # because references are broken
        # why doesn't this work? why are there 5 values in field_audits_ids?
        # field_audit_ids = field_audits.values_list('id', flat=True)
        field_audit_ids = [field_audit.id for field_audit in field_audits]
        field_audits = Audit.objects.filter(pk__in=field_audit_ids)

        for field_audit in field_audits:
            attached_review_audit = Audit.objects.get(pk=field_audit.ref.pk)

            self.assertEqual(attached_review_audit.action,
                             Audit.Type.PendingReject)

            self.assertNotEqual(None,
                                Audit.objects.get(
                                    model=field_audit.model,
                                    field=field_audit.field,
                                    model_id=field_audit.model_id,
                                    action=Audit.Type.PendingApprove))

    @skip("Insert pending approval not implemented at this time")
    def test_approve_insert_without_required_raises_integrity_error(self):
        new_plot = Plot(geom=self.p1, instance=self.instance)
        new_plot.save_with_user(self.pending_user)

        new_tree = Tree(plot=new_plot, instance=self.instance,
                        diameter=10, height=10, readonly=False)
        new_tree.save_with_user(self.pending_user)

        approve_or_reject_audits_and_apply(
            new_plot.audits(),
            self.commander_user, True)

        diameter_audit = Audit.objects.get(model='Tree',
                                           field='diameter',
                                           model_id=new_tree.pk)
        insert_audit = Audit.objects.get(model='Tree',
                                         model_id=new_tree.pk,
                                         field='id')

        approve_or_reject_audit_and_apply(
            diameter_audit, self.commander_user, approved=True)

        self.assertRaises(IntegrityError, approve_or_reject_audit_and_apply,
                          insert_audit, self.commander_user, True)

    @skip('Pending udfs are not implemented')
    def test_pending_udf_audits(self):
        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'choice',
                                 'choices': ['1', '2', '3']}),
            iscollection=False,
            name='times climbed')

        set_write_permissions(self.instance, self.commander_user,
                              'Plot', ['udf:times climbed'])

        FieldPermission.objects.create(
            model_name='Plot',
            field_name='udf:times climbed',
            permission_level=FieldPermission.WRITE_WITH_AUDIT,
            role=self.pending_user.get_instance_user(self.instance).role,
            instance=self.instance)

        initial_plot = Plot(geom=self.p1, instance=self.instance)
        initial_plot.udfs['times climbed'] = '2'
        initial_plot.save_with_user(self.pending_user)

        udf_audit = Audit.objects.get(model='Plot', field='udf:times climbed',
                                      model_id=initial_plot.pk)
        approve_or_reject_audit_and_apply(udf_audit, self.commander_user,
                                          approved=True)

        geom_audit = Audit.objects.get(model='Plot', field='geom',
                                       model_id=initial_plot.pk)
        approve_or_reject_audit_and_apply(geom_audit, self.commander_user,
                                          approved=True)

        readonly_audit = Audit.objects.get(model='Plot', field='readonly',
                                           model_id=initial_plot.pk)
        approve_or_reject_audit_and_apply(readonly_audit,
                                          self.commander_user, approved=True)

        insert_audit = Audit.objects.get(model='Plot', field='id',
                                         model_id=initial_plot.pk)

        approve_or_reject_audit_and_apply(insert_audit,
                                          self.commander_user, approved=True)

        new_plot = Plot.objects.get(pk=initial_plot.pk)

        self.assertEqual(new_plot.pk, initial_plot.pk)
        self.assertEqual(new_plot.readonly, False)
        self.assertEqual(new_plot.geom, self.p1)
        self.assertEqual(new_plot.udfs['times climbed'], '2')

    @skip("Insert pending approval not implemented at this time")
    def test_lots_of_trees_and_plots(self):
        """
        Make 3 plots: 2 pending and 1 approved
        Make 4 trees: 1 on each pending plot, 2 on approved plot
        Approve one pending plot.
        Approve all trees. The one on the (Still) pending plot
        should fail. all else should pass.
        """
        plot1 = Plot(geom=self.instance.center, instance=self.instance)
        plot2 = Plot(geom=self.instance.center, instance=self.instance)
        plot3 = Plot(geom=self.instance.center, instance=self.instance)
        plot1.save_with_user(self.commander_user)
        plot2.save_with_user(self.pending_user)
        plot3.save_with_user(self.pending_user)
        tree1 = Tree(plot=plot1, instance=self.instance)
        tree1.save_with_user(self.pending_user)
        tree2 = Tree(plot=plot1, instance=self.instance)
        tree2.save_with_user(self.pending_user)
        tree3 = Tree(plot=plot2, instance=self.instance)
        tree3.save_with_user(self.pending_user)
        tree4 = Tree(plot=plot3, instance=self.instance)
        tree4.save_with_user(self.pending_user)

        approve_or_reject_audits_and_apply(
            plot2.audits(),
            self.commander_user, True)

        approve_or_reject_audits_and_apply(
            tree1.audits(),
            self.commander_user, True)

        approve_or_reject_audits_and_apply(
            tree2.audits(),
            self.commander_user, True)

        approve_or_reject_audits_and_apply(
            tree3.audits(),
            self.commander_user, True)

        self.assertRaises(ObjectDoesNotExist, Plot.objects.get, pk=plot3.pk)
        self.assertRaises(ObjectDoesNotExist,
                          approve_or_reject_audits_and_apply,
                          tree4.audits(),
                          self.commander_user, True)


class ReputationTest(OTMTestCase):
    def setUp(self):
        self.p1 = Point(-7615441.0, 5953519.0)
        self.instance = make_instance(point=self.p1)

        self.commander = make_commander_user(self.instance)
        self.privileged_user = make_officer_user(self.instance)
        self.unprivileged_user = make_apprentice_user(self.instance)

        self.plot = Plot(geom=self.p1, instance=self.instance)

        self.plot.save_with_user(self.commander)

        rm = ReputationMetric(instance=self.instance, model_name='Tree',
                              action=Audit.Type.Insert, direct_write_score=2,
                              approval_score=20, denial_score=5)
        rm.save()

    def test_reputations_increase_for_direct_writes(self):
        self.assertEqual(self.privileged_user.get_reputation(self.instance), 0)
        t = Tree(plot=self.plot, instance=self.instance,
                 readonly=True)
        t.save_with_user(self.privileged_user)
        user = User.objects.get(pk=self.privileged_user.id)
        reputation = user.get_reputation(self.instance)
        self.assertGreater(reputation, 0)

    def test_reputation_metric_no_adjustment_for_no_rm_record(self):
        audit = Audit(model='Plot', model_id=1,
                      action=Audit.Type.Insert,
                      instance=self.instance, field='readonly',
                      previous_value=None,
                      current_value=True,
                      user=self.privileged_user)

        ReputationMetric.apply_adjustment(audit)

        self.assertEqual(0,
                         self.privileged_user.get_reputation(self.instance))

    def test_reputation_metric_positive_adjustment_for_rm(self):
        self.assertEqual(0,
                         self.unprivileged_user.get_reputation(self.instance))
        audit = Audit(model='Tree', model_id=1,
                      action=Audit.Type.Insert,
                      instance=self.instance, field='readonly',
                      previous_value=None,
                      current_value=True,
                      user=self.unprivileged_user)

        ReputationMetric.apply_adjustment(audit)

        self.assertEqual(2,
                         self.unprivileged_user.get_reputation(self.instance))

    def _test_negative_adjustment(self, initial, adjusted):
        iuser = self.unprivileged_user.get_instance_user(self.instance)
        iuser.reputation = initial
        iuser.save_base()

        audit = Audit(model='Tree', model_id=1,
                      action=Audit.Type.Insert,
                      instance=self.instance, field='readonly',
                      previous_value=None,
                      current_value=True,
                      user=self.unprivileged_user,
                      requires_auth=True)
        audit.save()
        self.assertEqual(initial, iuser.reputation)

        review_audit = Audit(model='Tree', model_id=1,
                             action=Audit.Type.PendingReject,
                             instance=self.instance, field='readonly',
                             previous_value=None,
                             current_value=True,
                             user=self.privileged_user)
        review_audit.save()

        audit.ref = review_audit
        audit.save()

        # requery iuser
        iuser = self.unprivileged_user.get_instance_user(self.instance)
        self.assertEqual(adjusted, iuser.reputation)

    def test_reputation_metric_negative_adjustment(self):
        self._test_negative_adjustment(10, 5)
        self._test_negative_adjustment(5, 0)
        self._test_negative_adjustment(3, 0)


class UserRoleFieldPermissionTest(MultiUserTestCase):
    def setUp(self):
        super(UserRoleFieldPermissionTest, self).setUp()

        self.plot = Plot(geom=self.p1, instance=self.instance)
        self.plot.save_with_user(self.commander_user)

        self.tree = Tree(plot=self.plot, instance=self.instance)
        self.tree.save_with_user(self.direct_user)

    def test_no_permission_cant_edit_object(self):
        self.plot.length = 10
        self.assertRaises(AuthorizeException,
                          self.plot.save_with_user, self.outlaw_user)

        self.assertNotEqual(Plot.objects.get(pk=self.plot.pk).length, 10)

        self.tree.diameter = 10
        self.assertRaises(AuthorizeException,
                          self.tree.save_with_user, self.outlaw_user)

        self.assertNotEqual(Tree.objects.get(pk=self.tree.pk).diameter, 10)

    def test_readonly_cant_edit_object(self):
        self.plot.length = 10
        self.assertRaises(AuthorizeException,
                          self.plot.save_with_user, self.observer_user)

        self.assertNotEqual(Plot.objects.get(pk=self.plot.pk).length, 10)

        self.tree.diameter = 10
        self.assertRaises(AuthorizeException,
                          self.tree.save_with_user, self.observer_user)

        self.assertNotEqual(Tree.objects.get(pk=self.tree.pk).diameter, 10)

    def test_writeperm_allows_write(self):
        self.plot.length = 10
        self.plot.save_with_user(self.direct_user)
        self.assertEqual(Plot.objects.get(pk=self.plot.pk).length, 10)

        self.tree.diameter = 10
        self.tree.save_with_user(self.direct_user)
        self.assertEqual(Tree.objects.get(pk=self.tree.pk).diameter, 10)

    def test_masking_authorized(self):
        "When masking with a superuser, nothing should happen"
        self.plot.width = 5
        self.plot.save_with_user(self.commander_user)

        plot = Plot.objects.get(pk=self.plot.pk)
        plot.mask_unauthorized_fields(self.commander_user)
        self.assertEqual(self.plot.width, plot.width)

    def test_masking_unauthorized(self):
        "Masking changes an unauthorized field to None"
        self.plot.width = 5
        self.plot.save_base()

        plot = Plot.objects.get(pk=self.plot.pk)
        plot.mask_unauthorized_fields(self.observer_user)
        self.assertEqual(plot.width, None)
        # geom is always readable
        self.assertEqual(plot.geom, self.plot.geom)

        plot = Plot.objects.get(pk=self.plot.pk)
        plot.mask_unauthorized_fields(self.outlaw_user)
        self.assertEqual(plot.width, None)
        # geom is always readable
        self.assertEqual(plot.geom, self.plot.geom)

    def test_write_fails_if_any_fields_cant_be_written(self):
        """ If a user tries to modify several fields simultaneously,
        only some of which s/he has access to, the write will fail
        for all fields."""
        self.plot.length = 10
        self.plot.width = 110

        self.assertRaises(AuthorizeException,
                          self.plot.save_with_user, self.direct_user)

        self.assertNotEqual(Plot.objects.get(pk=self.plot.pk).length, 10)
        self.assertNotEqual(Plot.objects.get(pk=self.plot.pk).width, 110)

        self.tree.diameter = 10
        self.tree.canopy_height = 110

        self.assertRaises(AuthorizeException, self.tree.save_with_user,
                          self.direct_user)

        self.assertNotEqual(Tree.objects.get(pk=self.tree.pk).diameter,
                            10)

        self.assertNotEqual(Tree.objects.get(pk=self.tree.pk).canopy_height,
                            110)


class UserRoleModelPermissionTest(MultiUserTestCase):
    def setUp(self):
        super(UserRoleModelPermissionTest, self).setUp()

        self.plot = Plot(geom=self.p1, instance=self.instance)
        self.plot.save_with_user(self.direct_user)

        self.tree = Tree(plot=self.plot, instance=self.instance)
        self.tree.save_with_user(self.direct_user)

    def _change_user_role(self, user, role):
        iuser = user.get_instance_user(self.instance)
        iuser.role = role
        iuser.save_with_user(self.commander_user)

    def test_save_new_object_authorized_officer(self):
        ''' Save two new objects with authorized user,
        nothing should happen'''
        plot = Plot(geom=self.p1, instance=self.instance)

        plot.save_with_user(self.direct_user)

        tree = Tree(plot=plot, instance=self.instance)

        tree.save_with_user(self.direct_user)

    def test_save_new_object_authorized_conjurer(self):
        ''' Save two new objects with authorized user,
        nothing should happen'''
        plot = Plot(geom=self.p1, instance=self.instance)

        plot.save_with_user(self.conjurer_user)

        tree = Tree(plot=plot, instance=self.instance)

        tree.save_with_user(self.conjurer_user)

    def test_save_new_object_unauthorized_outlaw(self):
        plot = Plot(geom=self.p1, instance=self.instance)

        self.assertRaises(AuthorizeException,
                          plot.save_with_user, self.outlaw_user)

        plot.save_base()
        tree = Tree(plot=plot, instance=self.instance)

        self.assertRaises(AuthorizeException,
                          tree.save_with_user, self.outlaw_user)

    def test_save_new_object_unauthorized_tweaker(self):
        plot = Plot(geom=self.p1, instance=self.instance)

        self.assertRaises(AuthorizeException,
                          plot.save_with_user, self.tweaker_user)

        plot.save_base()
        tree = Tree(plot=plot, instance=self.instance)

        self.assertRaises(AuthorizeException,
                          tree.save_with_user, self.tweaker_user)

    def test_assign_commander_role_can_delete(self):
        with self.assertRaises(AuthorizeException):
            self.tree.delete_with_user(self.outlaw_user)

        self._change_user_role(
            self.outlaw_user, make_commander_role(self.tree.get_instance()))

        self.tree.delete_with_user(self.outlaw_user)
        self.assertEqual(Tree.objects.count(), 0)

    def test_delete_object(self):
        with self.assertRaises(AuthorizeException):
            self.tree.delete_with_user(self.outlaw_user)
        self.tree.delete_with_user(self.commander_user)

        with self.assertRaises(AuthorizeException):
            self.plot.delete_with_user(self.outlaw_user, cascade=True)
        self.plot.delete_with_user(self.commander_user, cascade=True)

    def test_delete_object_you_created(self):
        outlaw_role = self.outlaw_user.get_role(self.instance)
        self._change_user_role(self.direct_user, outlaw_role)
        self.tree.delete_with_user(self.direct_user)
        self.plot.delete_with_user(self.direct_user, cascade=True)


class UserCanDeleteTestCase(OTMTestCase):
    def setUp(self):
        instance = make_instance()
        # Fancy name, but no write, create, or delete permissions
        instance.default_role.name = Role.ADMINISTRATOR

        self.creator_user = make_officer_user(instance)
        self.admin_user = make_admin_user(instance)
        self.other_user = make_observer_user(instance, username='other')
        self.tweaker_user = make_tweaker_user(instance)
        self.conjurer_user = make_conjurer_user(instance)

        self.plot = Plot(geom=instance.center, instance=instance)
        self.plot.save_with_user(self.creator_user)

        self.tree = Tree(plot=self.plot, instance=instance)
        self.tree.save_with_user(self.creator_user)

        self.rainBarrel = RainBarrel(geom=instance.center, instance=instance,
                                     capacity=5)
        self.rainBarrel.save_with_user(self.creator_user)

    def assert_can_delete(self, user, deletable, should_be_able_to_delete):
        can = deletable.user_can_delete(user)
        self.assertEqual(can, should_be_able_to_delete)

    def test_user_can_delete(self):
        self.assert_can_delete(self.conjurer_user, self.plot, True)
        self.assert_can_delete(self.conjurer_user, self.rainBarrel, True)
        self.assert_can_delete(self.conjurer_user, self.tree, True)

        self.assert_can_delete(self.creator_user, self.plot, True)
        self.assert_can_delete(self.creator_user, self.rainBarrel, True)
        self.assert_can_delete(self.creator_user, self.tree, True)

        self.assert_can_delete(self.admin_user, self.plot, True)
        self.assert_can_delete(self.admin_user, self.rainBarrel, True)
        self.assert_can_delete(self.admin_user, self.tree, True)

    def test_user_cannot_delete(self):
        self.assert_can_delete(self.tweaker_user, self.plot, False)
        self.assert_can_delete(self.tweaker_user, self.rainBarrel, False)
        self.assert_can_delete(self.tweaker_user, self.tree, False)

        self.assert_can_delete(self.other_user, self.plot, False)
        self.assert_can_delete(self.other_user, self.rainBarrel, False)
        self.assert_can_delete(self.other_user, self.tree, False)

    def test_admin_cannot_delete_by_flag(self):
        instance = self.tree.get_instance()
        role = self.admin_user.get_role(instance)
        role.instance_permissions.clear()

        self.assertTrue(self.admin_user.get_instance_user(instance).admin)
        self.assertEqual(role.instance_permissions.count(), 0)

        self.assert_can_delete(self.admin_user, self.tree, False)


class FieldPermMgmtTest(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.commander = make_commander_user(self.instance)

        self.new_role = Role(name='Ambassador', instance=self.instance,
                             rep_thresh=0)
        self.new_role.save()

        self.factory = RequestFactory()

    def assertInvalidFPRaises(self, **kwargs):
        fp = FieldPermission(**kwargs)
        fp.role = self.instance.default_role
        fp.instance = self.instance
        self.assertRaises(ValidationError, fp.save)

    def test_invalid_model_does_not_exist_unit(self):
        self.assertInvalidFPRaises(model_name='Gethen', field_name='readonly')

    def test_invalid_model_does_not_authorizable_unit(self):
        self.assertInvalidFPRaises(model_name='FieldPermission',
                                   field_name='role')

    def test_invalid_field_name_unit(self):
        self.assertInvalidFPRaises(model_name='Tree', field_name='model_name')


class AuditDetailTagTest(OTMTestCase):

    def setUp(self):
        self.p1 = Point(-8515222.0, 4953200.0)

        self.instance = make_instance(point=self.p1)
        self.user = make_commander_user(self.instance)

        self.plot = Plot(geom=self.p1, instance=self.instance)
        self.plot.save_with_user(self.user)

        self.tree = Tree(
            plot=self.plot, instance=self.instance, readonly=False)
        self.tree.save_with_user(self.user)

    def test_tree_link(self):
        audit = self.tree.audits()[0]
        link = audit_detail_link(audit)

        target = reverse('tree_detail',
                         kwargs={'instance_url_name': self.instance.url_name,
                                 'feature_id': self.tree.plot.pk,
                                 'tree_id': self.tree.pk})

        self.assertEqual(link, target)

    def test_plot_link(self):
        audit = self.plot.audits()[0]
        link = audit_detail_link(audit)

        target = reverse('map_feature_detail',
                         kwargs={'instance_url_name': self.instance.url_name,
                                 'feature_id': self.plot.pk})

        self.assertEqual(link, target)

    def test_bad_model_returns_none(self):
        audit = self.plot.audits()[0]
        audit.model = 'invaild'

        self.assertIsNone(audit_detail_link(audit))

    def test_bad_id_returns_none(self):
        audit = self.plot.audits()[0]
        audit.model_id = -1000

        self.assertIsNone(audit_detail_link(audit))


class SaveWithoutVerifyingTest(MultiUserTestCase):
    def setUp(self):
        super(SaveWithoutVerifyingTest, self).setUp()

        self.plot = Plot(geom=self.p1, instance=self.instance)
        self.plot.save_with_user(self.direct_user)

    def tests_works_when_normal_save_fails(self):
        self.plot = self.plot
        self.plot.width = 444
        with self.assertRaises(AuthorizeException):
            self.plot.save_with_user(User.system_user())
        self.plot.save_with_system_user_bypass_auth()

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import psycopg2
import json

from django.test import TestCase
from django.core.exceptions import (FieldError, ValidationError,
                                    ObjectDoesNotExist)
from django.db import IntegrityError, connection
from django.contrib.gis.geos import Point

from treemap.models import (Tree, Instance, Plot, Species, FieldPermission,
                            User, InstanceUser)

from treemap.audit import (Audit, UserTrackingException,
                           AuthorizeException, ReputationMetric,
                           approve_or_reject_audit_and_apply,
                           get_id_sequence_name)

from treemap.udf import UserDefinedFieldDefinition

from treemap.tests import (make_instance, make_user_with_default_role,
                           make_user_and_role, make_commander_user,
                           make_officer_user, make_observer_user,
                           make_apprentice_user, add_field_permissions)


class ScopeModelTest(TestCase):
    """
    Tests that the various operations on models are scoped to the
    instance they exist within. In general, ForeignKey relationships
    must either be to objects with the same instance, or objects that
    live outside of instance scoping (like Species).
    """

    def setUp(self):
        self.p1 = Point(-8515222.0, 4953200.0)
        self.p2 = Point(-7515222.0, 3953200.0)

        self.instance1 = make_instance()
        self.user = make_user_with_default_role(self.instance1, 'auser')
        self.global_role = self.instance1.default_role

        self.instance2 = make_instance(name='i2')
        self.instance2.save()

        iuser = InstanceUser(instance=self.instance2, user=self.user,
                             role=self.global_role)
        iuser.save_with_user(self.user)

        for i in [self.instance1, self.instance2]:
            FieldPermission(model_name='Plot', field_name='geom',
                            permission_level=FieldPermission.WRITE_DIRECTLY,
                            role=self.global_role,
                            instance=i).save()
            FieldPermission(model_name='Tree', field_name='plot',
                            permission_level=FieldPermission.WRITE_DIRECTLY,
                            role=self.global_role,
                            instance=i).save()

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

        for tc in tree_combos:
            plot, instance, readonly = tc
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

        self.assertRaises(FieldError, self.instance1.scope_model, Species)

    def test_plot_tree_same_instance(self):
        plot = Plot(geom=self.p1, instance=self.instance2)
        plot.save_with_user(self.user)

        tree = Tree(plot=plot, instance=self.instance1, readonly=False)
        self.assertRaises(ValidationError, tree.save_with_user, self.user)


class AuditTest(TestCase):

    def setUp(self):
        inst = self.instance = make_instance()

        permissions = (
            ('Plot', 'geom', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'id', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'plot', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'species', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'import_event', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'readonly', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'diameter', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'height', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'canopy_height', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'date_planted', FieldPermission.WRITE_DIRECTLY),
            ('Tree', 'date_removed', FieldPermission.WRITE_DIRECTLY))

        self.user1 = make_user_and_role(inst, 'charles', 'role1', permissions)
        self.user2 = make_user_and_role(inst, 'amy', 'role2', permissions)

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
        plot = Plot(geom=p, instance=self.instance)
        self.assertRaises(UserTrackingException, plot.save)
        self.assertRaises(UserTrackingException, plot.delete)

        tree = Tree()
        self.assertRaises(UserTrackingException, tree.save)
        self.assertRaises(UserTrackingException, tree.delete)

    def test_basic_audit(self):
        p = Point(-8515222.0, 4953200.0)
        plot = Plot(geom=p, instance=self.instance)
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
        self.assertEqual(get_id_sequence_name(Plot), 'treemap_plot_id_seq')


class PendingTest(TestCase):
    def setUp(self):
        self.instance = make_instance()
        self.commander_user = make_commander_user(self.instance)
        self.direct_user = make_officer_user(self.instance)
        self.pending_user = make_apprentice_user(self.instance)
        self.observer_user = make_observer_user(self.instance)

        self.p1 = Point(-7615441.0, 5953519.0)
        self.plot = Plot(geom=self.p1, instance=self.instance)
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


class PendingInsertTest(TestCase):

    def setUp(self):
        psycopg2.extras.register_hstore(connection.cursor(), globally=True)

        self.instance = make_instance()
        self.commander_user = make_commander_user(self.instance)
        self.pending_user = make_apprentice_user(self.instance)
        self.p1 = Point(-7615441.0, 5953519.0)

        # we need there to be no audits so that we can
        # iterate over all audits without conflict
        Audit.objects.all().delete()

    def approve_audits_with_insert_last(self, model_name, model_class,
                                        model_id=None,
                                        apply_assertions=False):

        # put the insert at the end so it can be approved last
        field_audits = Audit.objects.filter(model=model_name)\
                                    .exclude(field='id')

        insert_audits = Audit.objects.filter(model=model_name,
                                             field='id')

        if model_id:
            field_audits = field_audits.filter(model_id=model_id)
            insert_audit = insert_audits.get(model_id=model_id)
        else:
            if insert_audits.count() > 1:
                raise Exception("multiple possible insert audits."
                                "it's unclear what is expected to "
                                "happen.")
            else:
                insert_audit = insert_audits[0]

        field_audits = list(field_audits)

        for field_audit in field_audits:
            approve_or_reject_audit_and_apply(
                field_audit, self.commander_user, approved=True)
            if apply_assertions:
                if field_audit != field_audits[-1]:
                    self.assertEquals(model_class.objects.count(), 0)

        insert_audit = Audit.objects.get(id=insert_audit.id)

        approve_or_reject_audit_and_apply(
            insert_audit, self.commander_user, approved=True)

        if apply_assertions:
                self.assertEquals(model_class.objects.count(), 1)

    def test_insert_writes_when_approved(self):

        new_plot = Plot(geom=self.p1, instance=self.instance)
        new_plot.save_with_user(self.pending_user)

        new_tree = Tree(plot=new_plot, instance=self.instance)
        new_tree.save_with_user(self.pending_user)

        self.assertEquals(Plot.objects.count(), 0)
        self.assertEquals(Tree.objects.count(), 0)

        self.approve_audits_with_insert_last('Plot', Plot,
                                             apply_assertions=True)

        self.approve_audits_with_insert_last('Tree', Tree,
                                             apply_assertions=True)

    def test_record_is_created_when_nullables_are_still_pending(self):
        new_plot = Plot(geom=self.p1, instance=self.instance)
        new_plot.save_with_user(self.pending_user)

        new_tree = Tree(plot=new_plot, instance=self.instance,
                        diameter=10, height=10, readonly=False)

        new_tree.save_with_user(self.pending_user)

        self.approve_audits_with_insert_last('Plot', Plot)

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
            attached_review_audit = Audit.objects.get(pk=field_audit.ref_id.pk)

            self.assertEqual(attached_review_audit.action,
                             Audit.Type.PendingReject)

            self.assertNotEqual(None,
                                Audit.objects.get(
                                    model=field_audit.model,
                                    field=field_audit.field,
                                    model_id=field_audit.model_id,
                                    action=Audit.Type.PendingApprove))

    def test_approve_insert_without_required_raises_integrity_error(self):
        new_plot = Plot(geom=self.p1, instance=self.instance)
        new_plot.save_with_user(self.pending_user)

        new_tree = Tree(plot=new_plot, instance=self.instance,
                        diameter=10, height=10, readonly=False)
        new_tree.save_with_user(self.pending_user)

        self.approve_audits_with_insert_last('Plot', Plot)

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

    def test_pending_udf_audits(self):
        UserDefinedFieldDefinition.objects.create(
            instance=self.instance,
            model_type='Plot',
            datatype=json.dumps({'type': 'choice',
                                 'choices': ['1', '2', '3']}),
            iscollection=False,
            name='times_climbed')

        add_field_permissions(self.instance, self.commander_user,
                              'Plot', ['times_climbed'])

        FieldPermission.objects.create(
            model_name='Plot',
            field_name='times_climbed',
            permission_level=FieldPermission.WRITE_WITH_AUDIT,
            role=self.pending_user.get_instance_user(self.instance).role,
            instance=self.instance)

        initial_plot = Plot(geom=self.p1, instance=self.instance)
        initial_plot.udf_scalar_values['times_climbed'] = '2'
        initial_plot.save_with_user(self.pending_user)

        udf_audit = Audit.objects.get(model='Plot', field='times_climbed',
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
        self.assertEqual(new_plot.udf_scalar_values['times_climbed'], '2')

    def test_lots_of_trees_and_plots(self):
        """
        Make 3 plots: 2 pending and 1 approved
        Make 4 trees: 1 on each pending plot, 2 on approved plot
        Approve one pending plot.
        Approve all trees. The one on the (Still) pending plot
        should fail. all else should pass.
        """
        p1 = Point(0, 0)
        p2 = Point(1, 1)
        p3 = Point(2, 2)
        plot1 = Plot(geom=p1, instance=self.instance)
        plot2 = Plot(geom=p2, instance=self.instance)
        plot3 = Plot(geom=p3, instance=self.instance)
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

        self.approve_audits_with_insert_last('Plot', Plot,
                                             model_id=plot2.pk)
        self.approve_audits_with_insert_last('Tree', Tree,
                                             model_id=tree1.pk)
        self.approve_audits_with_insert_last('Tree', Tree,
                                             model_id=tree2.pk)
        self.approve_audits_with_insert_last('Tree', Tree,
                                             model_id=tree3.pk)

        self.assertRaises(ObjectDoesNotExist, Plot.objects.get, pk=plot3.pk)
        self.assertRaises(IntegrityError, self.approve_audits_with_insert_last,
                          'Tree', Tree, tree4.pk)


class ReputationTest(TestCase):
    def setUp(self):
        self.instance = make_instance()

        self.commander = make_commander_user(self.instance)
        self.privileged_user = make_officer_user(self.instance)
        self.unprivileged_user = make_apprentice_user(self.instance)

        self.p1 = Point(-7615441.0, 5953519.0)
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


class UserRoleFieldPermissionTest(TestCase):
    def setUp(self):
        self.instance = make_instance()
        self.commander = make_commander_user(self.instance)
        self.officer = make_officer_user(self.instance)
        self.observer = make_observer_user(self.instance)
        self.outlaw = make_user_with_default_role(self.instance, 'outlaw')

        self.p1 = Point(-8515941.0, 4953519.0)
        self.plot = Plot(geom=self.p1, instance=self.instance)
        self.plot.save_with_user(self.officer)

        self.tree = Tree(plot=self.plot, instance=self.instance)
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
        plot = Plot(geom=self.p1, instance=self.instance)

        plot.save_with_user(self.officer)

        tree = Tree(plot=plot, instance=self.instance)

        tree.save_with_user(self.officer)

    def test_save_new_object_unauthorized(self):
        plot = Plot(geom=self.p1, instance=self.instance)

        self.assertRaises(AuthorizeException,
                          plot.save_with_user, self.outlaw)

        plot.save_base()
        tree = Tree(plot=plot, instance=self.instance)

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

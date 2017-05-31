# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json

from django.contrib.auth.models import Permission
from django.test.utils import override_settings
from django.test.client import RequestFactory
from django.core.exceptions import ValidationError
from django.core import mail

from manage_treemap.views.roles import roles_update
from opentreemap.util import dotted_split
from treemap.instance import Instance
from treemap.models import User, InstanceUser
from treemap.tests import (make_instance, make_commander_user, make_request,
                           make_permission)
from treemap.tests.base import OTMTestCase
from treemap.audit import Role, FieldPermission

from manage_treemap.models import InstanceInvitation
from manage_treemap.views.user_roles import create_user_role, update_user_roles


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    CAN_ADD_USER_FUNCTION=None,
    INSTANCE_OWNER_FUNCTION=None)
class UserRolesTest(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.commander = make_commander_user(self.instance, "comm")

        # Note unicode '⅀' is on purpose
        self.user1 = User(username='estraven', password='estraven',
                          email='estraven@example.com',
                          organization='org111',
                          first_name='therem', last_name='⅀straven')

        self.user1.save_with_user(self.commander)

        self.user2 = User(username='genly', password='genly',
                          email='genly@example.com',
                          first_name='genly', last_name='ai')
        self.user2.save_with_user(self.commander)

        self.user3 = User(username='argaven_xv', password='argaven_xv',
                          email='argaven_xv@example.com')
        self.user3.save_with_user(self.commander)

        self.user4 = User(username='faxe', password='faxe',
                          email='faxe@example.com')
        self.user4.save_with_user(self.commander)

        self.factory = RequestFactory()

    def _add_user_to_instance_view(self, email):
            body = {'email': email}
            return create_user_role(
                make_request(method='POST',
                             body=json.dumps(body),
                             user=self.commander),
                self.instance)

    def test_add_user_to_instance(self):
        mail.outbox = []

        self.assertIsNone(self.user4.get_instance_user(self.instance))

        self._add_user_to_instance_view(self.user4.email)

        self.assertIsNotNone(self.user4.get_instance_user(self.instance))

        msg = mail.outbox[0]

        # Just make sure we have some chars and the
        # correct receiver
        self.assertGreater(len(msg.subject), 10)
        self.assertGreater(len(msg.body), 10)

        self.assertEquals(tuple(msg.to), (self.user4.email,))

    def test_email_not_found_creates_invite(self):
        self.assertEqual(InstanceInvitation.objects.count(), 0)

        mail.outbox = []

        email = 'some@email.com'
        body = {'email': email}
        create_user_role(
            make_request(method='POST',
                         body=json.dumps(body),
                         user=self.commander),
            self.instance)

        self.assertEqual(InstanceInvitation.objects.count(), 1)

        ii = InstanceInvitation.objects.all()[0]

        # Should have email and default role
        self.assertEqual(ii.email, email)
        self.assertEqual(ii.instance, self.instance)
        self.assertEqual(ii.role, self.instance.default_role)

        # Should have sent an email to the user
        self.assertEqual(len(mail.outbox), 1)

        msg = mail.outbox[0]

        # Just make sure we have some chars and the
        # correct receiver
        self.assertGreater(len(msg.subject), 10)
        self.assertGreater(len(msg.body), 10)

        self.assertEquals(tuple(msg.to), (email,))

    def test_invalid_email(self):
        body = {'email': 'asdfasdf@'}
        self.assertRaises(ValidationError,
                          create_user_role,
                          make_request(method='POST',
                                       body=json.dumps(body),
                                       user=self.commander),
                          self.instance)

    def test_email_already_bound(self):
        iuser = InstanceUser(user=self.user1, instance=self.instance,
                             role=self.instance.default_role)
        iuser.save_with_user(self.commander)

        body = {'email': self.user1.email}
        self.assertRaises(ValidationError,
                          create_user_role,
                          make_request(method='POST',
                                       body=json.dumps(body),
                                       user=self.commander),
                          self.instance)

    def test_email_already_bound_to_invite(self):
        email = "blah@blahhhh.com"
        invite = InstanceInvitation(email=email,
                                    instance=self.instance,
                                    created_by=self.user4,
                                    role=self.instance.default_role)
        invite.save()

        body = {'email': email}
        self.assertRaises(ValidationError,
                          create_user_role,
                          make_request(method='POST',
                                       body=json.dumps(body),
                                       user=self.commander),
                          self.instance)

    def test_invites_updated(self):
        email = "blah@blahhhh.com"
        invite = InstanceInvitation(email=email,
                                    instance=self.instance,
                                    created_by=self.user4,
                                    role=self.instance.default_role)
        invite.save()

        new_role = Role(name='Ambassador', instance=self.instance,
                        rep_thresh=0)
        new_role.save()

        body = {'invites':
                {invite.pk:
                 {'role': new_role.pk}}}

        update_user_roles(
            make_request(method='POST',
                         body=json.dumps(body),
                         user=self.commander),
            self.instance)

        # requery invite
        invite = InstanceInvitation.objects.get(pk=invite.pk)
        self.assertEqual(invite.role, new_role)

    def test_user_roles_updated(self):
        iuser = InstanceUser(user=self.user2, instance=self.instance,
                             role=self.instance.default_role)
        iuser.save_with_user(self.commander)

        new_role = Role(name='Ambassador', instance=self.instance,
                        rep_thresh=0)
        new_role.save()

        body = {'users':
                {iuser.pk:
                 {'role': new_role.pk, 'admin': False}}}

        update_user_roles(
            make_request(method='POST',
                         body=json.dumps(body),
                         user=self.commander),
            self.instance)

        #requery iuser
        iuser = InstanceUser.objects.get(pk=iuser.pk)
        self.assertEqual(iuser.role, new_role)
        self.assertEqual(iuser.admin, False)

        body = {'users':
                {iuser.pk: {'role': new_role.pk, 'admin': True}}}

        update_user_roles(
            make_request(method='POST',
                         body=json.dumps(body),
                         user=self.commander),
            self.instance)

        #requery iuser
        iuser = InstanceUser.objects.get(pk=iuser.pk)
        self.assertEqual(iuser.role, new_role)
        self.assertEqual(iuser.admin, True)

    def test_can_change_admin_without_feature(self):
        iuser = InstanceUser(user=self.user2, instance=self.instance,
                             role=self.instance.default_role)
        iuser.save_with_user(self.commander)

        body = {'users':
                {iuser.pk: {'admin': False}}}

        update_user_roles(
            make_request(method='POST',
                         body=json.dumps(body),
                         user=self.commander),
            self.instance)

        #requery iuser
        iuser = InstanceUser.objects.get(pk=iuser.pk)
        self.assertEqual(iuser.admin, False)

        body = {'users':
                {iuser.pk: {'admin': True}}}

        update_user_roles(
            make_request(method='POST',
                         body=json.dumps(body),
                         user=self.commander),
            self.instance)

        #requery iuser
        iuser = InstanceUser.objects.get(pk=iuser.pk)
        self.assertEqual(iuser.admin, True)


@override_settings(FEATURE_BACKEND_FUNCTION=None)
class ModelPermMgmtTest(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()

        self.commander = make_commander_user(self.instance)

        self.new_role = Role(name='Ambassador', instance=self.instance,
                             rep_thresh=0)
        self.new_role.save()

        self.factory = RequestFactory()

        self.RolePermissionModel = Role.instance_permissions.through

    def request_updates(self, perm_specs):
        updates = {self.new_role.pk: {'fields': {}, 'models': perm_specs}}
        request = make_request(method='PUT', body=json.dumps(updates))
        roles_update(request, self.instance)

    def assert_assignment(self, permission, role, is_assigned=True):
        assignment = self.RolePermissionModel.objects.filter(
            role=role, permission=permission)
        self.assertEqual(assignment.exists(), is_assigned)

    def test_instance_assignment(self):
        permission = make_permission('do_all_the_things', Instance)
        self.request_updates({'Instance.do_all_the_things': True})

        self.assert_assignment(permission, self.new_role)

    def test_model_assignment(self):
        self.instance.add_map_feature_types(['Bioswale'])
        permissions = [
            'Plot.add_plot',
            'Plot.delete_plot',
            'Tree.add_tree',
            'Tree.delete_tree',
            'TreePhoto.add_treephoto',
            'TreePhoto.delete_treephoto',
            'Bioswale.add_bioswale',
            'Bioswale.delete_bioswale',
            'MapFeaturePhoto.add_bioswalephoto',
            'MapFeaturePhoto.delete_bioswalephoto']

        self.request_updates(
            dict(zip(permissions, [True] * len(permissions))))

        for existing in permissions:
            __, codename = dotted_split(existing, 2, maxsplit=1)
            permission = Permission.objects.get(codename=codename)
            self.assert_assignment(permission, self.new_role)

    def test_unassignment(self):
        instance_permission = make_permission('do_all_the_things', Instance)
        add_plot_permission = Permission.objects.get(codename='add_plot')
        self.assertIsNotNone(instance_permission)
        self.assertIsNotNone(add_plot_permission)

        self.RolePermissionModel.objects.bulk_create([
            self.RolePermissionModel(
                role=self.new_role, permission=instance_permission),
            self.RolePermissionModel(
                role=self.new_role, permission=add_plot_permission)])

        self.assertEqual(
            self.RolePermissionModel.objects.filter(
                role=self.new_role).count(), 2)

        self.request_updates({
            'Instance.do_all_the_things': False,
            'Plot.add_plot': False})

        self.assertEqual(
            self.RolePermissionModel.objects.filter(
                role=self.new_role).count(), 0)


class FieldPermMgmtTest(OTMTestCase):
    def setUp(self):
        self.instance = make_instance()
        self.commander = make_commander_user(self.instance)

        self.new_role = Role(name='Ambassador', instance=self.instance,
                             rep_thresh=0)
        self.new_role.save()

        self.factory = RequestFactory()

    def make_updates(self, role_id, field_json):
        return {
            role_id: {
                'fields': field_json,
                'models': {}
            }
        }

    def test_updates(self):

        # TODO: For now, don't use '2', which is pending
        updates = self.make_updates(
            self.new_role.pk, {'Tree.diameter': 3})

        json_updates = json.dumps(updates)
        request = make_request(method='PUT', body=json_updates)
        roles_update(request, self.instance)

        #requery new_role
        self.new_role = Role.objects.get(pk=self.new_role.pk)

        self.assertEqual(1,
                         FieldPermission.objects.filter(
                             model_name='Tree',
                             field_name='diameter',
                             instance=self.instance,
                             role=self.new_role,
                             permission_level=3).count())

    def test_no_updates(self):
        updates = {}

        json_updates = json.dumps(updates)
        request = make_request(method='PUT', body=json_updates)
        roles_update(request, self.instance)

    def assertUpdatesRaisesValidation(self, updates):
        json_updates = json.dumps(updates)
        request = make_request(method='PUT', body=json_updates)
        self.assertRaises(ValidationError, roles_update,
                          request, self.instance)

    def test_invalid_model_does_not_exist_integration(self):
        updates = self.make_updates(
            self.new_role.pk, {'Gethen.model_name': 2})
        self.assertUpdatesRaisesValidation(updates)

    def test_invalid_model_not_authorizable_integration(self):
        updates = self.make_updates(
            self.new_role.pk, {'FieldPermission.model_name': 2})
        self.assertUpdatesRaisesValidation(updates)

    def test_invalid_field_name_integration(self):
        updates = self.make_updates(
            self.new_role.pk, {'Tree.model_name': 2})
        self.assertUpdatesRaisesValidation(updates)

    def test_invalid_role_id_integration(self):
        updates = self.make_updates(
            100, {'Tree.readonly': 2})
        self.assertUpdatesRaisesValidation(updates)

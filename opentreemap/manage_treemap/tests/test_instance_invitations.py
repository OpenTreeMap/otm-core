# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from registration.models import RegistrationProfile

from django.core import mail
from django.http import HttpRequest
from django.test import override_settings

from treemap.models import User, InstanceUser
from treemap.tests import make_user, make_instance
from treemap.tests.test_urls import UrlTestCase

from registration_backend.views import (RegistrationView, ActivationView,
                                        RegistrationForm)

from manage_treemap.models import InstanceInvitation


class InstanceInvitationTest(UrlTestCase):
    class MockSession(dict):
        def cycle_key(self):
            pass

    def setUp(self):
        self.user = make_user(username='test', password='password')
        self.instance = make_instance()

        # Create an admin user to verify that not all admins get notifications
        self.admin = make_user(instance=self.instance, username='admin',
                               admin=True)

    def _login(self):
        self.client.post('/accounts/login/',
                         {'username': 'test',
                          'password': 'password'})

    def _make_registration_view(self):
        rv = RegistrationView()
        rv.request = self._make_request()
        return rv

    def _make_request(self):
        request = HttpRequest()
        request.META = {'SERVER_NAME': 'localhost',
                        'SERVER_PORT': '80'}
        request.session = self.MockSession()
        return request

    def test_normal_registration_without_invite(self):
        mail.outbox = []

        email = "arst@neio.com"

        rv = self._make_registration_view()
        form = RegistrationForm(data={
            'email': email,
            'email2': email,
            'username': "u1",
            'password1': "pass",
            'password2': "pass"
        })
        self.assertTrue(form.is_valid())
        rv.register(form)

        users = User.objects.filter(email=email)
        self.assertTrue(users.exists())

        user = users[0]

        self.assertFalse(user.is_active)
        self.assertEquals(len(InstanceUser.objects.filter(user=user)), 0)

        success_url = rv.get_success_url(user)
        self.assertEqual(success_url, 'registration_complete')

    def _invite_and_register(self, invite_email, user_email=None,
                             key_matches=True):
        if user_email is None:
            user_email = invite_email

        invite = InstanceInvitation.objects.create(
            created_by=self.user,
            instance=self.instance,
            email=invite_email,
            role=self.instance.default_role)

        # Clear the outbox after creating the instance so that emails
        # triggered by instance creation do not affect this test
        mail.outbox = []

        rv = self._make_registration_view()

        if key_matches:
            rv.request.GET = {'key': invite.activation_key}

        form = RegistrationForm(data={
            'email': user_email,
            'email2': user_email,
            'username': "u1",
            'password1': "pass",
            'password2': "pass"
        })
        self.assertTrue(form.is_valid())
        rv.register(form)

        return rv

    def assert_user_was_invited(self, view, new_user):
        self.assertTrue(new_user.is_active)
        self.assertIsNotNone(new_user.get_instance_user(self.instance))

        success_url, __, __ = view.get_success_url(new_user)
        self.assertEqual(success_url, '/%s/map/' % self.instance.url_name)

        self.assertEquals(len(mail.outbox), 1)
        msg = mail.outbox[0]

        # Make sure we have some chars and the correct receivers
        self.assertGreater(len(msg.subject), 10)
        self.assertGreater(len(msg.body), 10)
        to = set(msg.to)
        expected_to = {self.user.email}
        self.assertEquals(to, expected_to)

    # Disable plug-in function to ensure we are testing core behavior
    @override_settings(INVITATION_ACCEPTED_NOTIFICATION_EMAILS=None)
    def test_adds_to_invited_instances_and_redirects(self):
        rv = self._invite_and_register("some@email.com")

        users = User.objects.filter(email="some@email.com")
        self.assertTrue(users.exists())

        new_user = users[0]
        self.assert_user_was_invited(rv, new_user)

    def test_does_not_redirect_when_email_different(self):
        rv = self._invite_and_register("some@email.com", "different@other.com")

        users = User.objects.filter(email="different@other.com")
        self.assertTrue(users.exists())

        new_user = users[0]

        # The email did not match the invite email, so the user should not be
        # activated (yet)
        self.assertFalse(new_user.is_active)
        self.assertIsNone(new_user.get_instance_user(self.instance))

        success_url = rv.get_success_url(new_user)
        self.assertEqual(success_url, 'registration_complete')

        # We should get an activation email, and no others, because the emails
        # did not match
        self.assertEquals(len(mail.outbox), 1)
        msg = mail.outbox[0]

        self.assertEquals(tuple(msg.to), (new_user.email,))

    def test_does_not_redirect_when_key_does_not_match(self):
        rv = self._invite_and_register("some@email.com", key_matches=False)

        users = User.objects.filter(email="some@email.com")
        self.assertTrue(users.exists())

        new_user = users[0]

        # The activation key did not match the invite key, so the user should
        # not be activated (yet)
        self.assertFalse(new_user.is_active)
        self.assertIsNone(new_user.get_instance_user(self.instance))

        success_url = rv.get_success_url(new_user)
        self.assertEqual(success_url, 'registration_complete')

        # We should get an activation email, and no others, because the emails
        # did not match
        self.assertEquals(len(mail.outbox), 1)
        msg = mail.outbox[0]

        self.assertEquals(tuple(msg.to), (new_user.email,))

    # Disable plug-in function to ensure we are testing core behavior
    @override_settings(INVITATION_ACCEPTED_NOTIFICATION_EMAILS=None)
    def test_adds_to_invited_instances_after_activation(self):
        self._invite_and_register("some@email.com", "different@other.com")

        users = User.objects.filter(email="different@other.com")
        self.assertTrue(users.exists())

        new_user = users[0]
        reg_profile = RegistrationProfile.objects.get(user=new_user)

        av = ActivationView()
        av.request = self._make_request()

        mail.outbox = []

        activated_user = av.activate(activation_key=reg_profile.activation_key)

        # All the things that were true for the same email case should be true
        # now that we have activated via email loop, even though the user's
        # email is different from the original invite (since the keys match)
        self.assert_user_was_invited(av, activated_user)

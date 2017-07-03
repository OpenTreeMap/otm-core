# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.contrib.sessions.middleware import SessionMiddleware
from django.test.utils import override_settings

from treemap.util import add_visited_instance, get_last_visited_instance
from treemap.models import InstanceUser
from treemap.tests import (ViewTestCase, make_instance, make_request,
                           make_user_with_default_role)


@override_settings(ROOT_URLCONF='treemap.tests.unit_test_urls')
class VisitedInstancesTests(ViewTestCase):
    def setUp(self):
        super(VisitedInstancesTests, self).setUp()
        self.instance1 = make_instance(1, is_public=True)
        self.instance2 = make_instance(2, is_public=True)
        self.instance3 = make_instance(3, is_public=False)
        self.instance4 = make_instance(4, is_public=False)

        self.user = make_user_with_default_role(self.instance, 'joe')
        self.user.set_password('joe')
        self.user.save()

        self.request = make_request(user=self.user)

        InstanceUser(
            instance=self.instance4,
            user=self.user,
            role=self.instance4.default_role).save_base()

        middleware = SessionMiddleware()
        middleware.process_request(self.request)
        self.request.session.save()

    def _format(self, number):
        # Allow tests to work with --keepdb
        return '{:,d}'.format(number)

    def test_session(self):
        #
        # Create a view that renders a simple template
        # that reads the `last_instance` from the context
        # processor (that should be inserted by the session)
        #
        # By default, nothing is in session
        self.assertEqual(self.client.get('/test-last-instance').content, '')

        # Going to an instance sets the context variable
        self.client.get('/%s/map/' % self.instance1.url_name)
        self.assertEqual(self.client.get('/test-last-instance').content,
                         self._format(self.instance1.pk))

        # Going to a non-public instance doesn't update it
        self.client.get('/%s/map/' % self.instance3.url_name)
        self.assertEqual(self.client.get('/test-last-instance').content,
                         self._format(self.instance1.pk))

        # Going to a private instance while not logged in
        # also doesn't update
        self.client.get('/%s/map/' % self.instance4.url_name)
        self.assertEqual(self.client.get('/test-last-instance').content,
                         self._format(self.instance1.pk))

        self.client.login(username='joe', password='joe')

        # But should change after logging in
        self.client.get('/%s/map/' % self.instance4.url_name)
        self.assertEqual(self.client.get('/test-last-instance').content,
                         self._format(self.instance4.pk))

    def test_get_last_instance(self):
        add_visited_instance(self.request, self.instance1)
        self.assertEqual(self.instance1,
                         get_last_visited_instance(self.request))

        add_visited_instance(self.request, self.instance2)
        self.assertEqual(self.instance2,
                         get_last_visited_instance(self.request))

        add_visited_instance(self.request, self.instance1)
        self.assertEqual(self.instance1,
                         get_last_visited_instance(self.request))

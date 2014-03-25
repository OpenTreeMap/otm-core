# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.core.urlresolvers import reverse
from django.core import mail

from registration.models import RegistrationProfile

from treemap.tests.ui import UITestCase
from treemap.tests import make_user, create_mock_system_user

# Testing requirements:
# apt-get install firefox
# pip install -r requirements.txt
# pip install -r test-requirements.txt


class LoginLogoutTest(UITestCase):
    def setUp(self):

        create_mock_system_user()

        super(LoginLogoutTest, self).setUp()
        self.user = make_user(username='username', password='password')
        self.profile = RegistrationProfile.objects.create_profile(self.user)

    def test_invalid_login(self):
        self.browse_to_url(reverse('auth_login'))

        login_url = self.driver.current_url

        self.process_login_form(
            self.user.username, 'passwordinvalid')

        # We should be on the same page
        self.assertEqual(login_url, self.driver.current_url)

        # There should be an error div with at least one
        # element
        errors = self.driver.find_elements_by_css_selector('.errorlist li')
        self.assertEqual(len(errors), 1)

    def test_valid_login(self):
        self.browse_to_url(reverse('auth_login'))

        login_url = self.driver.current_url

        self.click('#login')
        self.process_login_form(self.user.username, 'password')

        # We should not be on the same page
        self.assertNotEqual(login_url, self.driver.current_url)

        # And we should expect our username in the url
        self.assertIn(self.user.username, self.driver.current_url)

        emails = self.driver.find_elements_by_xpath(
            "//*[@data-field='user.email']")

        self.assertGreater(len(emails), 0, 'data-field = user.email not found')

        founddisplay = False
        for email_elmt in emails:
            value = email_elmt.get_attribute('data-value')
            dataclass = email_elmt.get_attribute('data-class')
            if dataclass == 'display':
                self.assertEqual(self.user.email, value)
                founddisplay = True

        if not founddisplay:
            self.fail('No display list element was found')


class ForgotUsernameTest(UITestCase):
    def setUp(self):

        create_mock_system_user()

        super(ForgotUsernameTest, self).setUp()
        self.user = make_user(username='username', password='password')

    def tearDown(self):
        mail.outbox = []
        super(ForgotUsernameTest, self).tearDown()

    def test_can_get_to_page(self):
        self.browse_to_url(reverse('auth_login'))

        forgot_username_url = reverse('forgot_username')

        link = self.find_anchor_by_url(forgot_username_url)

        link.click()

        self.assertEqual(self.live_server_url + forgot_username_url,
                         self.driver.current_url)

    def test_can_retrieve_username(self):
        self.browse_to_url(reverse('forgot_username'))

        email_elem = self.driver.find_element_by_name('email')

        email_elem.send_keys(self.user.email)

        self.click('form input[type="submit"]')

        self.assertEqual(len(mail.outbox), 1)

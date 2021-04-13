# -*- coding: utf-8 -*-


from time import sleep
from django.urls import reverse
from django.core import mail

from registration.models import RegistrationProfile

from treemap.tests.ui import UITestCase
from treemap.tests import make_user, create_mock_system_user


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

        # There should be an error list with at least one element
        self.wait_until_present('.errorlist li')

        # We should be on the same page
        self.assertEqual(login_url, self.driver.current_url)

    def test_valid_login(self):
        self.browse_to_url(reverse('auth_login'))

        login_url = self.driver.current_url

        self.process_login_form(self.user.username, 'password')

        email_element = self.wait_until_present(
            '[data-field="user.email"][data-class="display"]')

        # We should not be on the same page
        self.assertNotEqual(login_url, self.driver.current_url)

        # We should expect our username in the url
        self.assertIn(self.user.username, self.driver.current_url)

        value = email_element.get_attribute('data-value')
        self.assertEqual(self.user.email, value)

        sleep(1)  # prevent hang


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
        self.wait_until_present('input[name="email"]')

        self.assertEqual(self.live_server_url + forgot_username_url,
                         self.driver.current_url)

    def test_can_retrieve_username(self):
        self.browse_to_url(reverse('forgot_username'))

        email_elem = self.driver.find_element_by_name('email')

        email_elem.send_keys(self.user.email)

        self.click('form input[type="submit"]')
        self.wait_until_text_present('Email Sent')

        self.assertEqual(len(mail.outbox), 1)

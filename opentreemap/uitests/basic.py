from unittest import TestCase
from treemap.models import User
from registration.models import RegistrationProfile

import uitests

# Testing requirements:
# apt-get install firefox
# pip install -r requirements.txt
# Selenium
# PyVirtualDisplay
userUUID = 1


class LoginLogoutTest(TestCase):
    def setUp(self):
        self.driver = uitests.driver

        self.user = self._create_test_user()
        self.profile = RegistrationProfile.objects.create_profile(self.user)

    def tearDown(self):
        self.user.delete_with_user(User.system_user())

    def _create_test_user(self):
        global userUUID

        username = 'autotest%s' % userUUID
        userUUID += 1

        u = User(username=username, email='%s@testing.org' % username)
        u.set_password(username)
        u.save()
        setattr(u, 'plain_password', username)

        return u

    def _process_login_form(self, username, password):
        username_elmt = self.driver.find_element_by_name('username')
        password_elmt = self.driver.find_element_by_name('password')

        username_elmt.send_keys(username)
        password_elmt.send_keys(password)

        submit = self.driver.find_element_by_css_selector('form * button')
        submit.click()

    def test_invalid_login(self):
        self.driver.get("http://localhost/")

        # find the element that's name attribute is q (the google search box)
        login = self.driver.find_element_by_id("login")
        login.click()

        login_url = self.driver.current_url

        self._process_login_form(
            self.user.username, self.user.plain_password + 'invalid')

        # We should be on the same page
        self.assertEqual(login_url, self.driver.current_url)

        # There should be an error div with at least one
        # element
        errors = self.driver.find_elements_by_css_selector('.errorlist li')
        self.assertEqual(len(errors), 1)

    def test_valid_login(self):
        self.driver.get("http://localhost/")

        login_url = self.driver.current_url

        # find the element that's name attribute is q (the google search box)
        login = self.driver.find_element_by_id("login")
        login.click()

        self._process_login_form(
            self.user.username, self.user.plain_password)

        # We should not be on the same page
        self.assertNotEqual(login_url, self.driver.current_url)

        # And we should expect our username in the url
        self.assertIn(self.user.username, self.driver.current_url)

        emails = self.driver.find_elements_by_xpath(
            "//li[@data-field='user.email']")

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

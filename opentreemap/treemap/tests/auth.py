from treemap.tests import RequestTestCase
from treemap.tests import make_instance_and_basic_user


def make_instance_and_user(username, password):
    instance, user = make_instance_and_basic_user()
    user.username = username
    user.set_password(password)
    user.save_base()
    return instance, user


class LogoutTests(RequestTestCase):
    def test_logout(self):
        res = self.client.get('/accounts/logout/')
        self.assertOk(res)


class LoginTests(RequestTestCase):

    def setUp(self):
        self.client.get('/accounts/logout/')
        self.username = 'testo'
        self.password = '1337'
        self.instance, self.user = make_instance_and_user(
            self.username, self.password)

    def test_password_correct(self):

        res = self.client.post('/accounts/login/',
                               {'username': self.username,
                                'password': self.password})
        self.assertTemporaryRedirect(res,
                                     'http://testserver/accounts/profile/')

    def test_successful_login_redirect(self):
        self.client.post('/accounts/login/',
                         {'username': self.username,
                          'password': self.password})
        res = self.client.get('/accounts/profile/')
        expected_url = 'http://testserver/users/%s/' % self.username
        self.assertTemporaryRedirect(res, expected_url)

    def test_password_incorrect(self):
        res = self.client.post('/accounts/login/',
                               {'username': self.username,
                                'password': 'WRONG!'})
        # If your login is invalid, the POST returns 200 and the user
        # stays on the login form page.
        self.assertOk(res)

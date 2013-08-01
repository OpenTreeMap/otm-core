from treemap.models import User
from treemap.tests import RequestTestCase, make_instance


class LogoutTests(RequestTestCase):
    def test_logout(self):
        res = self.client.get('/accounts/logout/')
        self.assertOk(res)


class LoginTests(RequestTestCase):

    def setUp(self):
        self.client.get('/accounts/logout/')
        self.username = 'testo'
        self.password = '1337'
        self.instance = make_instance()
        self.user = User(username=self.username)
        self.user.set_password(self.password)
        self.user.save()

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

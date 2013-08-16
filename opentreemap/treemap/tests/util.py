from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.contrib.sessions.middleware import SessionMiddleware

from treemap.util import (add_visited_instance, get_last_visited_instance)

from treemap.tests import (ViewTestCase, make_instance,
                           make_user_with_default_role)


class VisitedInstancesTests(ViewTestCase):
    def setUp(self):
        super(VisitedInstancesTests, self).setUp()
        self.instance1 = make_instance(1)
        self.instance2 = make_instance(2)

        self.user = make_user_with_default_role(self.instance, 'joe')
        self.request = self._make_request(user=self.user)

        middleware = SessionMiddleware()
        middleware.process_request(self.request)
        self.request.session.save()

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

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import logging

from cStringIO import StringIO

from django.test import TestCase
from django.test.client import RequestFactory
from django.test.simple import DjangoTestSuiteRunner
from django.conf import settings
from django.db.models import Max

from django.contrib.gis.geos import Point, Polygon, MultiPolygon
from django.contrib.auth.models import AnonymousUser

from django.template import Template, RequestContext
from django.http import HttpResponse
from django.conf.urls import patterns

from treemap.models import User, InstanceUser

from djcelery.contrib.test_runner import CeleryTestSuiteRunner


class OTM2TestRunner(CeleryTestSuiteRunner, DjangoTestSuiteRunner):
    def run_tests(self, *args, **kwargs):
        logging.disable(logging.CRITICAL)
        return super(OTM2TestRunner, self).run_tests(*args, **kwargs)

    def build_suite(self, test_labels, *args, **kwargs):
        test_labels = test_labels or settings.MANAGED_APPS
        return super(OTM2TestRunner, self).build_suite(test_labels,
                                                       *args,
                                                       **kwargs)


def make_simple_boundary(name, n=1):
    b = Boundary()
    b.geom = MultiPolygon(make_simple_polygon(n))
    b.name = name
    b.category = "Unknown"
    b.sort_order = 1
    b.save()
    return b


def make_simple_polygon(n=1):
    """
    Creates a simple, point-like polygon for testing distances
    so it will save to the geom field on a Boundary.

    The idea is to create small polygons such that the n-value
    that is passed in can identify how far the polygon will be
    from the origin.

    For example:
    p1 = make_simple_polygon(1)
    p2 = make_simple_polygon(2)

    p1 will be closer to the origin.
    """
    return Polygon(((n, n), (n, n + 1), (n + 1, n + 1), (n, n)))


def _add_permissions(instance, role, permissions):
    if permissions:
        for perm in permissions:
            model_name, field_name, permission_level = perm
            FieldPermission.objects.get_or_create(
                model_name=model_name, field_name=field_name,
                permission_level=permission_level, role=role,
                instance=instance)


def make_loaded_role(instance, name, rep_thresh, permissions):
    role, created = Role.objects.get_or_create(
        name=name, instance=instance, rep_thresh=rep_thresh)

    role.save()
    _add_permissions(instance, role, permissions)
    return role


def add_field_permissions(instance, user, model_type, field_names):
    permissions = ()
    for field in field_names:
        permissions += ((model_type, field, FieldPermission.WRITE_DIRECTLY),)
    role = user.get_role(instance)
    _add_permissions(instance, role, permissions)


def _make_permissions(field_permission):
    permissions = (
        ('Plot', 'geom', field_permission),
        ('Plot', 'width', field_permission),
        ('Plot', 'length', field_permission),
        ('Plot', 'address_street', field_permission),
        ('Plot', 'address_city', field_permission),
        ('Plot', 'address_zip', field_permission),
        ('Plot', 'import_event', field_permission),
        ('Plot', 'owner_orig_id', field_permission),
        ('Plot', 'readonly', field_permission),
        ('Tree', 'plot', field_permission),
        ('Tree', 'species', field_permission),
        ('Tree', 'import_event', field_permission),
        ('Tree', 'readonly', field_permission),
        ('Tree', 'diameter', field_permission),
        ('Tree', 'height', field_permission),
        ('Tree', 'canopy_height', field_permission),
        ('Tree', 'date_planted', field_permission),
        ('Tree', 'date_removed', field_permission),
        ('TreePhoto', 'thumbnail', field_permission),
        ('TreePhoto', 'tree', field_permission),
        ('TreePhoto', 'image', field_permission),
        ('Species', 'otm_code', field_permission),
        ('Species', 'common_name', field_permission),
        ('Species', 'genus', field_permission),
        ('Species', 'species', field_permission),
        ('Species', 'cultivar', field_permission),
        ('Species', 'other', field_permission),
        ('Species', 'native_status', field_permission),
        ('Species', 'gender', field_permission),
        ('Species', 'bloom_period', field_permission),
        ('Species', 'fruit_period', field_permission),
        ('Species', 'fall_conspicuous', field_permission),
        ('Species', 'flower_conspicuous', field_permission),
        ('Species', 'palatable_human', field_permission),
        ('Species', 'wildlife_value', field_permission),
        ('Species', 'fact_sheet', field_permission),
        ('Species', 'plant_guide', field_permission),
        ('Species', 'max_dbh', field_permission),
        ('Species', 'max_height', field_permission))
    return permissions


def make_commander_role(instance, extra_plot_fields=None):
    """
    The commander role has permission to modify all model fields
    directly for all models under test.
    """
    permissions = _make_permissions(FieldPermission.WRITE_DIRECTLY)
    commander_permissions = (
        ('Plot', 'id', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'id', FieldPermission.WRITE_DIRECTLY),
        ('TreePhoto', 'id', FieldPermission.WRITE_DIRECTLY),
        ('Species', 'id', FieldPermission.WRITE_DIRECTLY)
    )

    permissions = permissions + commander_permissions
    if extra_plot_fields:
        for field in extra_plot_fields:
            permissions += (('Plot', field, FieldPermission.WRITE_DIRECTLY),)

    return make_loaded_role(instance, 'commander', 3, permissions)


def make_officer_role(instance):
    """
    The officer role has permission to modify only a few fields,
    and only a few models under test, but the officer is permitted to
    modify them directly without moderation.
    """
    permissions = (
        ('Plot', 'geom', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'length', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'readonly', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'diameter', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'plot', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'height', FieldPermission.WRITE_DIRECTLY))
    return make_loaded_role(instance, 'officer', 3, permissions)


def make_apprentice_role(instance):
    """
    The apprentice role has permission to modify all model fields
    for all models under test, but its edits are subject to review.
    """
    permissions = _make_permissions(FieldPermission.WRITE_WITH_AUDIT)
    return make_loaded_role(instance, 'apprentice', 2, permissions)


def make_observer_role(instance):
    """
    The observer can read a few model fields.
    """
    permissions = (
        ('Plot', 'geom', FieldPermission.READ_ONLY),
        ('Plot', 'length', FieldPermission.READ_ONLY),
        ('Tree', 'diameter', FieldPermission.READ_ONLY),
        ('Tree', 'height', FieldPermission.READ_ONLY))
    return make_loaded_role(instance, 'observer', 2, permissions)


def make_plain_user(username, password='password'):
    user = User(username=username, email='%s@example.com' % username)
    user.set_password(password)  # hashes password, allowing authentication
    user.save()

    return user


def login(client, username):
    client.post('/accounts/login/', {'username': username,
                                     'password': 'password'})


def logout(client):
    client.get('/accounts/logout/')


def make_user(instance=None, username='username', make_role=None,
              admin=False, password='password'):
    """
    Create a User with the given username, and an InstanceUser for the
    given instance. The InstanceUser's role comes from calling make_role()
    (if provided) or from the instance's default role.
    """
    user = make_plain_user(username, password)
    if instance:
        role = make_role(instance) if make_role else instance.default_role
        iuser = InstanceUser(instance=instance, user=user,
                             role=role, admin=admin)
        iuser.save_with_user(user)
    return user


def make_commander_user(instance, username='commander'):
    return make_user(instance, username, make_commander_role)


def make_admin_user(instance, username='admin'):
    return make_user(instance, username, make_commander_role, admin=True)


def make_officer_user(instance, username='officer'):
    return make_user(instance, username, make_officer_role)


def make_apprentice_user(instance, username='apprentice'):
    return make_user(instance, username, make_apprentice_role)


def make_observer_user(instance, username='observer'):
    return make_user(instance, username, make_observer_role)


def make_user_with_default_role(instance, username):
    return make_user(instance, username)


def make_user_and_role(instance, username, rolename, permissions):
    def make_role(instance):
        return make_loaded_role(instance, rolename, 2, permissions)

    return make_user(instance, username, make_role)


def delete_all_app_users():
    for app_user in User.objects.exclude(pk=User._system_user.pk):
        InstanceUser.objects.filter(user_id=app_user.pk).delete()
        app_user.delete_with_user(User._system_user)


def make_instance(name=None, is_public=False, url_name=None):
    if name is None:
        max_instance = Instance.objects.all().aggregate(
            Max('id'))['id__max'] or 0
        name = 'generated$%d' % (max_instance + 1)

    if url_name is None:
        max_instance = Instance.objects.all().aggregate(
            Max('id'))['id__max'] or 0
        url_name = 'generated-%d' % (max_instance + 1)

    global_role = Role.objects.filter(name='global', rep_thresh=0)
    if not global_role.exists():
        global_role = Role.objects.create(name='global', rep_thresh=0)
    else:
        global_role = global_role[0]

    p1 = Point(0, 0)

    instance = Instance(name=name, geo_rev=0, default_role=global_role,
                        is_public=is_public, url_name=url_name)

    tri = Polygon(((p1.x, p1.y),
                   (p1.x + 10, p1.y + 10),
                   (p1.x + 20, p1.y),
                   (p1.x, p1.y)))
    instance.bounds = MultiPolygon((tri,))
    instance.save()

    return instance


def create_mock_system_user():
    try:
        system_user = User.objects.get(username="system_user")
    except Exception:
        system_user = User(username="system_user",
                           email='noreplyx02x0@example.com')
        system_user.id = settings.SYSTEM_USER_ID

    User._system_user = system_user


def make_request(params={}, user=None, method='GET', body=None, file=None):
    if user is None:
        user = AnonymousUser()

    extra = {}
    if body:
        body_stream = StringIO(body)
        extra['wsgi.input'] = body_stream
        extra['CONTENT_LENGTH'] = len(body)

    if file:
        post_data = {'file': file}
        req = RequestFactory().post("hello/world", post_data, **extra)
    else:
        req = RequestFactory().get("hello/world", params, **extra)
        req.method = method

    setattr(req, 'user', user)

    return req


class ViewTestCase(TestCase):
    def _add_global_url(self, url, view_fn):
        """
        Insert a new url into treemap for Client resolution
        """
        from opentreemap import urls
        urls.urlpatterns += patterns(
            '', (url, view_fn))

    def _mock_request_with_template_string(self, template):
        """
        Create a new request that renders the given template
        with a normal request context
        """
        def mock_request(request):
            r = RequestContext(request)
            tpl = Template(template)

            return HttpResponse(tpl.render(r))

        return mock_request

    def setUp(self):
        self.factory = RequestFactory()
        self.instance = make_instance()

    def call_view(self, view, view_args=[], view_keyword_args={},
                  url="hello/world", url_args={}):
        request = self.factory.get(url, url_args)
        response = view(request, *view_args, **view_keyword_args)
        return json.loads(response.content)

    def call_instance_view(self, view, view_args=None, view_keyword_args={},
                           url="hello/world", url_args={}):
        if (view_args is None):
            view_args = [self.instance.pk]
        else:
            view_args.insert(0, self.instance.pk)

        return self.call_view(view, view_args, view_keyword_args,
                              url, url_args)


class RequestTestCase(TestCase):

    def assertOk(self, res):
        self.assertTrue(res.status_code >= 200 and res.status_code <= 200,
                        'expected the response to have a 2XX status code, '
                        'not %d' % res.status_code)


class MockSession():
    def __init__(self):
        self.modified = False
        self._dict = {}

    def __setitem__(self, key, val):
        self._dict[key] = val

    def __getitem__(self, key):
        return self._dict[key]

    def __iter__(self):
        return self._dict.__iter__()

    def get(self, name, default):
        if name in self._dict:
            return self._dict[name]
        else:
            return default


create_mock_system_user()

from templatetags import *  # NOQA
from udfs import *          # NOQA
from audit import *         # NOQA
from auth import *          # NOQA
from models import *        # NOQA
from search import *        # NOQA
from urls import *          # NOQA
from views import *         # NOQA
from util import *          # NOQA
from middleware import *    # NOQA
from json_field import *    # NOQA
from units import *    # NOQA

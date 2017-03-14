# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import logging
from cStringIO import StringIO
import subprocess
import shutil
import tempfile
import os
import json

from django.test.client import RequestFactory
from django.test.runner import DiscoverRunner
from django.conf import settings
from django.db.models import Max
from django.template import Template, RequestContext
from django.http import HttpResponse
from django.conf.urls import patterns

from django.contrib.gis.geos import Point, Polygon, MultiPolygon
from django.contrib.auth.models import AnonymousUser, Permission
from django.contrib.contenttypes.models import ContentType

from treemap.models import (User, InstanceUser, Boundary, FieldPermission,
                            Role)
from treemap.instance import Instance, InstanceBounds
from treemap.audit import Authorizable, add_default_permissions
from treemap.util import leaf_models_of_class
from treemap.tests.base import OTMTestCase

from djcelery.contrib.test_runner import CeleryTestSuiteRunner


class OTM2TestRunner(CeleryTestSuiteRunner, DiscoverRunner):

    def run_tests(self, *args, **kwargs):
        logging.disable(logging.CRITICAL)
        return super(OTM2TestRunner, self).run_tests(*args, **kwargs)

    def setup_databases(self, *args, **kwargs):
        # We want to load a system user, but until the test database is created
        # we can't, so we need to overload setup_databases and do it here
        result = super(OTM2TestRunner, self).setup_databases(*args, **kwargs)
        create_mock_system_user()
        return result


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
    return Polygon(((n, n), (n, n + 1), (n + 1, n + 1), (n + 1, n), (n, n)))


def _set_permissions(instance, role, permissions):
    for perm in permissions:
        model_name, field_name, permission_level = perm
        fp, __ = FieldPermission.objects.get_or_create(
            model_name=model_name, field_name=field_name, role=role,
            instance=instance)
        fp.permission_level = permission_level
        fp.save()


def _make_loaded_role(instance, name, default_permission_level, permissions=(),
                      rep_thresh=2):
    role, __ = Role.objects.get_or_create(
        name=name, instance=instance,
        default_permission_level=default_permission_level,
        rep_thresh=rep_thresh)
    role.save()

    add_default_permissions(instance, {role})
    _set_permissions(instance, role, permissions)

    return role


def _make_permissions(field_permission):
    def make_model_perms(Model):
        return tuple(
            (Model._meta.object_name, field_name, field_permission)
            for field_name in Model().tracked_fields)

    models = leaf_models_of_class(Authorizable)

    model_permissions = [make_model_perms(Model) for Model in models]
    permissions = sum(model_permissions, ())  # flatten
    return permissions


def make_commander_role(instance):
    """
    The commander role has permission to modify all model fields
    directly for all models under test.
    """
    return _make_loaded_role(instance, 'commander',
                             FieldPermission.WRITE_DIRECTLY)


def make_tweaker_role(instance, name='tweaker'):
    """
    The tweaker role has permission to modify all model fields
    directly for all models under test, but not create or delete.
    """
    permissions = []
    models = leaf_models_of_class(Authorizable)
    for Model in models:
        permissions += [
            (Model.__name__, fieldname,
             FieldPermission.WRITE_DIRECTLY)
            for fieldname in Model.requires_authorization]
    return _make_loaded_role(instance, name, FieldPermission.NONE,
                             permissions)


def make_conjurer_role(instance):
    """
    The conjurer role has permission to create and delete all models
    under test and their related photo types,
    but limited permission to read or write fields in them.
    """
    permissions = (
        ('Plot', 'length', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'height', FieldPermission.WRITE_DIRECTLY))
    conjurer = _make_loaded_role(instance, 'conjurer', FieldPermission.NONE,
                                 permissions)
    models = [Model for Model in leaf_models_of_class(Authorizable)
              if Model.__name__ in {'Plot', 'RainBarrel', 'Tree'}]
    ThroughModel = Role.instance_permissions.through
    model_permissions = Role.model_permissions(models)

    role_perms = [ThroughModel(role_id=conjurer.id, permission_id=perm.id)
                  for perm in model_permissions]
    ThroughModel.objects.bulk_create(role_perms)

    return conjurer


def make_officer_role(instance):
    """
    The officer role has permission to modify only a few fields,
    and only a few models under test, but the officer is permitted to
    modify them directly without moderation.
    """
    permissions = (
        ('Plot', 'length', FieldPermission.WRITE_DIRECTLY),
        ('RainBarrel', 'capacity', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'diameter', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'height', FieldPermission.WRITE_DIRECTLY))
    officer = _make_loaded_role(instance, 'officer', FieldPermission.NONE,
                                permissions)
    models = [Model for Model in leaf_models_of_class(Authorizable)
              if Model.__name__ in {'Plot', 'RainBarrel', 'Tree'}]
    officer.instance_permissions.add(*Role.model_permissions(models))
    officer.save()
    return officer


def make_apprentice_role(instance):
    """
    The apprentice role has permission to modify all model fields
    for all models under test, but its edits are subject to review.
    """
    return _make_loaded_role(instance, 'apprentice',
                             FieldPermission.WRITE_WITH_AUDIT)


def make_observer_role(instance):
    """
    The observer can read a few model fields.
    """
    permissions = (
        ('Plot', 'length', FieldPermission.READ_ONLY),
        ('RainBarrel', 'capacity', FieldPermission.READ_ONLY),
        ('Tree', 'diameter', FieldPermission.READ_ONLY),
        ('Tree', 'height', FieldPermission.READ_ONLY))
    return _make_loaded_role(instance, 'observer', FieldPermission.NONE,
                             permissions)


def set_invisible_permissions(instance, user, model_type, field_names):
    set_permissions(instance, user, model_type, field_names,
                    FieldPermission.NONE)


def set_read_permissions(instance, user, model_type, field_names):
    set_permissions(instance, user, model_type, field_names,
                    FieldPermission.READ_ONLY)


def set_write_permissions(instance, user, model_type, field_names):
    set_permissions(instance, user, model_type, field_names,
                    FieldPermission.WRITE_DIRECTLY)


def set_permissions(instance, user, model_type, field_names, perm):
    permissions = ()
    for field in field_names:
        permissions += ((model_type, field, perm),)
    role = user.get_role(instance)
    _set_permissions(instance, role, permissions)


def make_plain_user(username, password='password'):
    user = User(username=username, email='%s@example.com' % username)
    user.set_password(password)  # hashes password, allowing authentication
    user.save()

    return user


def make_instance_user(instance, user):
    iu = InstanceUser(instance=instance, user=user, role=instance.default_role)
    iu.save_with_user(User._system_user)


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


def make_commander_user(instance=None, username='commander'):
    return make_user(instance, username, make_commander_role)


def make_admin_user(instance, username='admin'):
    return make_user(instance, username, make_commander_role, admin=True)


def make_officer_user(instance, username='officer'):
    return make_user(instance, username, make_officer_role)


def make_apprentice_user(instance, username='apprentice'):
    return make_user(instance, username, make_apprentice_role)


def make_observer_user(instance, username='observer'):
    return make_user(instance, username, make_observer_role)


def make_tweaker_user(instance, username='tweaker'):
    return make_user(instance, username, make_tweaker_role)


def make_conjurer_user(instance, username='conjurer'):
    return make_user(instance, username, make_conjurer_role)


def make_user_with_default_role(instance, username):
    return make_user(instance, username)


def make_user_and_role(instance, username, rolename, field_permissions,
                       models_to_permit):
    def make_role(instance):
        role = _make_loaded_role(instance, rolename, FieldPermission.NONE,
                                 field_permissions)
        if models_to_permit:
            role.instance_permissions.add(
                *Role.model_permissions(models_to_permit))

        return role

    return make_user(instance, username, make_role)


def make_instance(name=None, is_public=False, url_name=None, point=None,
                  edge_length=600):
    if name is None:
        max_instance = Instance.objects.all().aggregate(
            Max('id'))['id__max'] or 0
        name = 'generated$%d' % (max_instance + 1)

    if url_name is None:
        max_instance = Instance.objects.all().aggregate(
            Max('id'))['id__max'] or 0
        url_name = 'generated-%d' % (max_instance + 1)

    p1 = point or Point(0, 0)

    instance = Instance(name=name, geo_rev=0,
                        is_public=is_public, url_name=url_name)

    instance.seed_with_dummy_default_role()

    d = edge_length / 2
    instance.bounds = InstanceBounds.create_from_point(p1.x, p1.y, d)
    instance.save()

    new_role = Role.objects.create(
        name='role-%s' % name, instance=instance,
        rep_thresh=0, default_permission_level=FieldPermission.READ_ONLY)

    instance.default_role = new_role
    instance.save()

    return instance


def create_mock_system_user():
    try:
        system_user = User.objects.get(id=settings.SYSTEM_USER_ID)
    except Exception:
        system_user = User(username="system_user",
                           email='noreplyx02x0@example.com')
        system_user.id = settings.SYSTEM_USER_ID
        system_user.set_password('password')
        system_user.save_base()

    User._system_user = system_user


def make_request(params={}, user=None, instance=None,
                 method='GET', body=None, file=None,
                 path='hello/world'):
    if user is None:
        user = AnonymousUser()

    extra = {}
    if body:
        body_stream = StringIO(body)
        extra['wsgi.input'] = body_stream
        extra['CONTENT_LENGTH'] = len(body)

    if file:
        post_data = {'file': file}
        req = RequestFactory().post(path, post_data, **extra)
    else:
        req = RequestFactory().get(path, params, **extra)
        req.method = method

    setattr(req, 'user', user)

    if instance:
        setattr(req, 'instance', instance)

    return req


def make_permission(codename, Model, name=None):
    perm, __ = Permission.objects.get_or_create(
        codename=codename,
        name=name or codename,
        content_type=ContentType.objects.get_for_model(Model))
    return perm


def media_dir(f):
    "Helper method for MediaTest classes to force a specific media dir"
    def m(self):
        with self._media_dir():
            f(self)
    return m


def ecoservice_not_running():
    """Returns True if the ecoservice is not running"""
    try:
        status = subprocess.check_output(
            ["service", settings.ECOSERVICE_NAME, "status"])
        return status.find('start/running') < 0
    except subprocess.CalledProcessError:
        return True


class LocalMediaTestCase(OTMTestCase):
    def setUp(self):
        self.photoDir = tempfile.mkdtemp()
        self.mediaUrl = '/testingmedia/'

    def _media_dir(self):
        return self.settings(DEFAULT_FILE_STORAGE=
                             'django.core.files.storage.FileSystemStorage',
                             MEDIA_ROOT=self.photoDir,
                             MEDIA_URL=self.mediaUrl)

    def resource_path(self, name):
        module_dir = os.path.dirname(__file__)
        path = os.path.join(module_dir, 'resources', name)

        return path

    def load_resource(self, name):
        return file(self.resource_path(name))

    def tearDown(self):
        shutil.rmtree(self.photoDir)

    def assertPathExists(self, path):
        self.assertTrue(os.path.exists(path), '%s does not exist' % path)

    def assertPathDoesNotExist(self, path):
        self.assertFalse(os.path.exists(path), '%s exists' % path)


class ViewTestCase(OTMTestCase):
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


class RequestTestCase(OTMTestCase):

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

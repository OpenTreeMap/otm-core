from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.test import TestCase
from django.test.client import RequestFactory

from django.contrib.gis.geos import Point, Polygon


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


def make_loaded_role(instance, name, rep_thresh, permissions):
    role, created = Role.objects.get_or_create(
        name=name, instance=instance, rep_thresh=rep_thresh)

    role.save()

    for perm in permissions:
        model_name, field_name, permission_level = perm
        FieldPermission.objects.get_or_create(
            model_name=model_name, field_name=field_name,
            permission_level=permission_level, role=role,
            instance=instance)

    return role


def make_god_role(instance):
    permissions = (
        ('Plot', 'instance', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'id', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'geom', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'width', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'length', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'address_street', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'address_city', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'address_zip', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'import_event', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'owner_orig_id', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'readonly', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'plot', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'id', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'instance', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'species', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'import_event', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'readonly', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'diameter', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'height', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'canopy_height', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'date_planted', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'date_removed', FieldPermission.WRITE_DIRECTLY))
    return make_loaded_role(instance, 'god', 3, permissions)


def make_commander_role(instance):
    permissions = (
        ('Plot', 'geom', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'width', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'length', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'address_street', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'address_city', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'address_zip', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'import_event', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'owner_orig_id', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'readonly', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'plot', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'species', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'import_event', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'readonly', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'diameter', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'height', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'canopy_height', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'date_planted', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'date_removed', FieldPermission.WRITE_DIRECTLY))
    return make_loaded_role(instance, 'commander', 3, permissions)


def make_officer_role(instance):
    permissions = (
        ('Plot', 'geom', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'length', FieldPermission.WRITE_DIRECTLY),
        ('Plot', 'readonly', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'diameter', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'plot', FieldPermission.WRITE_DIRECTLY),
        ('Tree', 'height', FieldPermission.WRITE_DIRECTLY))
    return make_loaded_role(instance, 'officer', 3, permissions)


def make_apprentice_role(instance):
    permissions = (
        ('Plot', 'geom', FieldPermission.WRITE_WITH_AUDIT),
        ('Plot', 'width', FieldPermission.WRITE_WITH_AUDIT),
        ('Plot', 'length', FieldPermission.WRITE_WITH_AUDIT),
        ('Plot', 'address_street', FieldPermission.WRITE_WITH_AUDIT),
        ('Plot', 'address_city', FieldPermission.WRITE_WITH_AUDIT),
        ('Plot', 'address_zip', FieldPermission.WRITE_WITH_AUDIT),
        ('Plot', 'import_event', FieldPermission.WRITE_WITH_AUDIT),
        ('Plot', 'owner_orig_id', FieldPermission.WRITE_WITH_AUDIT),
        ('Plot', 'readonly', FieldPermission.WRITE_WITH_AUDIT),
        ('Tree', 'plot', FieldPermission.WRITE_WITH_AUDIT),
        ('Tree', 'species', FieldPermission.WRITE_WITH_AUDIT),
        ('Tree', 'import_event', FieldPermission.WRITE_WITH_AUDIT),
        ('Tree', 'readonly', FieldPermission.WRITE_WITH_AUDIT),
        ('Tree', 'diameter', FieldPermission.WRITE_WITH_AUDIT),
        ('Tree', 'height', FieldPermission.WRITE_WITH_AUDIT),
        ('Tree', 'canopy_height', FieldPermission.WRITE_WITH_AUDIT),
        ('Tree', 'date_planted', FieldPermission.WRITE_WITH_AUDIT),
        ('Tree', 'date_removed', FieldPermission.WRITE_WITH_AUDIT))
    return make_loaded_role(instance, 'apprentice', 2, permissions)


def make_observer_role(instance):
    permissions = (
        ('Plot', 'geom', FieldPermission.READ_ONLY),
        ('Plot', 'length', FieldPermission.READ_ONLY),
        ('Tree', 'diameter', FieldPermission.READ_ONLY),
        ('Tree', 'height', FieldPermission.READ_ONLY))
    return make_loaded_role(instance, 'observer', 2, permissions)


def make_instance(name='i1'):
    global_role, _ = Role.objects.get_or_create(name='global', rep_thresh=0)

    p1 = Point(0, 0)

    instance, _ = Instance.objects.get_or_create(
        name=name, geo_rev=0, center=p1, default_role=global_role)

    return instance


def make_system_user():
    try:
        system_user = User.objects.get(username="system_user")
    except Exception:
        system_user = User(username="system_user")
        system_user.save_base()
    return system_user


def make_basic_user(instance, username):
    """ A helper function for making an instance and user

    You'll still want to load the permissions you need for each
    test onto the user's role. """
    system_user = make_system_user()

    user = User(username=username)
    user.save_with_user(system_user)
    return user


def make_instance_and_basic_user():
    instance = make_instance()
    basic_user = make_basic_user(instance, "custom_user")
    return instance, basic_user


def make_instance_and_system_user():
    instance = make_instance()
    system_user = make_system_user()
    return instance, system_user


class ViewTestCase(TestCase):
    def _make_request(self, params={}):
        return self.factory.get("hello/world", params)

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


from audit import *   # NOQA
from models import *  # NOQA
from search import *  # NOQA
from views import *   # NOQA

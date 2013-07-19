from django.contrib.gis.geos.collections import MultiPolygon
from django.contrib.gis.geos.point import Point
from django.contrib.gis.geos.polygon import Polygon
from api.models import APILog, APIKey

from treemap.models import (Species, Boundary, Tree, Plot,
                            ImportEvent, User)
from treemap.tests import (make_instance, make_commander_role,
                           make_system_user)

import django.shortcuts


def mkPlot(instance, user, geom=Point(50, 50)):
    p = Plot(geom=geom, instance=instance, created_by=user)
    p.save_with_user(user)

    return p


def mkTree(instance, user, plot=None, species=None):
    if not plot:
        plot = mkPlot(instance, user)

    if species is not None:
        s = Species.objects.all()[0]
    else:
        s = species

    t = Tree(plot=plot, instance=instance, species=s, created_by=user)
    t.save_with_user(user)

    return t


def setupTreemapEnv():
    def local_render_to_response(*args, **kwargs):
        from django.template import loader
        from django.http import HttpResponse

        httpresponse_kwargs = {'mimetype': kwargs.pop('mimetype', None)}
        hr = HttpResponse(
            loader.render_to_string(*args, **kwargs), **httpresponse_kwargs)

        if hasattr(args[1], 'dicts'):
            hr.request_context = args[1].dicts

        return hr

    django.shortcuts.render_to_response = local_render_to_response

    instance = make_instance()

    system_user = make_system_user()
    system_user.roles.add(make_commander_role(instance))

    u = User.objects.filter(username="jim")
    if u:
        u = u[0]
    else:
        u = User(username="jim", email="jim@test.org", password="jim")
        u.save_with_user(system_user)

    amy_filter_result = User.objects.filter(username="amy")
    if not amy_filter_result:
        amy = User(username="amy", email="amy@test.org", password="amy")
        amy.save_with_user(system_user)
        amy.roles.add(make_commander_role(instance))
    else:
        amy = amy_filter_result[0]

    olivia_filter_result = User.objects.filter(username="olivia")
    if not amy_filter_result:
        olivia = User(
            username="olivia", email="olivia@test.org", password="olivia")

        olivia.save_with_user(system_user)
        olivia.roles.add(make_commander_role(instance))
    else:
        olivia = olivia_filter_result[0]

    n1geom = MultiPolygon(Polygon(
        ((0, 0), (100, 0), (100, 100), (0, 100), (0, 0))))

    n2geom = MultiPolygon(
        Polygon(((0, 101), (101, 101), (101, 200), (0, 200), (0, 101))))

    n1 = Boundary(name="n1", category='blah', sort_order=4, geom=n1geom)
    n2 = Boundary(name="n2", category='blah', sort_order=4, geom=n2geom)

    n1.save()
    n2.save()

    s1 = Species(symbol="s1", genus="testus1", species="specieius1",
                 cultivar_name='', itree_code='BDL OTHER')
    s2 = Species(symbol="s2", genus="testus2", species="specieius2",
                 cultivar_name='', itree_code='BDL OTHER')
    s3 = Species(symbol="s3", genus="testus2", species="specieius3",
                 cultivar_name='', itree_code='BDL OTHER')

    s1.native_status = True
    s1.fall_conspicuous = True
    s1.flower_conspicuous = True
    s1.palatable_human = True

    s2.native_status = True
    s2.fall_conspicuous = False
    s2.flower_conspicuous = True
    s2.palatable_human = False
    s2.wildlife_value = True

    s3.wildlife_value = True

    s1.save()
    s2.save()
    s3.save()

    ie = ImportEvent(imported_by=system_user)
    ie.save()

    return instance


def teardownTreemapEnv():
    system_user = make_system_user()

    for r in APILog.objects.all():
        r.delete()

    for r in APIKey.objects.all():
        r.delete()

    for r in Tree.objects.all():
        r.delete_with_user(system_user)

    for r in Plot.objects.all():
        r.delete_with_user(system_user)

    for r in Boundary.objects.all():
        r.delete()

    for r in Species.objects.all():
        r.delete()

    for r in ImportEvent.objects.all():
        r.delete()

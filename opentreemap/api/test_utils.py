from django.contrib.gis.geos.collections import MultiPolygon
from django.contrib.gis.geos.point import Point
from django.contrib.gis.geos.polygon import Polygon
from api.models import APILog, APIKey

from treemap.models import (Species, Boundary, Tree, Plot, User, Instance)
from treemap.tests import (make_commander_role, make_instance,
                           make_commander_user, make_apprentice_user,
                           make_user_with_default_role)

import django.shortcuts


def mkPlot(instance, user, geom=Point(50, 50)):
    p = Plot(geom=geom, instance=instance)
    p.save_with_user(user)

    return p


def mkTree(instance, user, plot=None, species=None):
    if not plot:
        plot = mkPlot(instance, user)

    if species is not None:
        s = Species.objects.all()[0]
    else:
        s = species

    t = Tree(plot=plot, instance=instance, species=s)
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

    make_user_with_default_role(instance, 'jim')
    make_commander_user(instance, 'commander')
    make_apprentice_user(instance, 'apprentice')

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

    return instance


def teardownTreemapEnv():
    commander = User.objects.get(username="commander")

    for r in APILog.objects.all():
        r.delete()

    for r in APIKey.objects.all():
        r.delete()

    for r in Tree.objects.all():
        r.delete_with_user(commander)

    for r in Plot.objects.all():
        r.delete_with_user(commander)

    for r in Boundary.objects.all():
        r.delete()

    for r in Species.objects.all():
        r.delete()

from django.conf import settings

settings.POSTAL_CODE_FIELD = None # Use US Zip Code

from django.contrib.auth.models import User
from django.contrib.gis.geos.collections import MultiPolygon
from django.contrib.gis.geos.point import Point
from django.contrib.gis.geos.polygon import Polygon
from django_reputation.models import ReputationAction, Reputation
from api.models import APILog, APIKey
from profiles.models import UserProfile
from treemap.models import Species, BenefitValues, Resource, Neighborhood, ZipCode, ExclusionMask, AggregateNeighborhood, ImportEvent, Tree, Plot

import django.shortcuts

def mkPlot(u, geom=Point(50,50)):
    p = Plot(geometry=geom, last_updated_by=u, import_event=ImportEvent.objects.all()[0],present=True, data_owner=u)
    p.save()

    return p

def mkTree(u, plot=None, species=-1):
    if not plot:
        plot = mkPlot(u)

    if species == -1:
        s = Species.objects.all()[0]
    else:
        s = species

    t = Tree(plot=plot, species=s, last_updated_by=u, import_event=ImportEvent.objects.all()[0])
    t.present = True
    t.save()

    return t

def setupTreemapEnv():
    settings.GEOSERVER_GEO_LAYER = ""
    settings.GEOSERVER_GEO_STYLE = ""
    settings.GEOSERVER_URL = ""

    def local_render_to_response(*args, **kwargs):
        from django.template import loader, RequestContext
        from django.http import HttpResponse

        httpresponse_kwargs = {'mimetype': kwargs.pop('mimetype', None)}
        hr = HttpResponse(
            loader.render_to_string(*args, **kwargs), **httpresponse_kwargs)

        if hasattr(args[1], 'dicts'):
            hr.request_context = args[1].dicts

        return hr

    django.shortcuts.render_to_response = local_render_to_response

    r1 = ReputationAction(name="edit verified", description="blah")
    r2 = ReputationAction(name="edit tree", description="blah")
    r3 = ReputationAction(name="Administrative Action", description="blah")
    r4 = ReputationAction(name="add tree", description="blah")
    r5 = ReputationAction(name="edit plot", description="blah")
    r6 = ReputationAction(name="add plot", description="blah")
    r7 = ReputationAction(name="add stewardship", description="blah")
    r8 = ReputationAction(name="remove stewardship", description="blah")

    for r in [r1,r2,r3,r4,r5,r6,r7,r8]:
        r.save()

    bv = BenefitValues(co2=0.02, pm10=9.41, area="InlandValleys",
                       electricity=0.1166,voc=4.69,ozone=5.0032,natural_gas=1.25278,
                       nox=12.79,stormwater=0.0078,sox=3.72,bvoc=4.96)

    bv.save()

    dbh = "[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]"
    dbh2 = "[2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]"

    rsrc1 = Resource(meta_species="BDM_OTHER", electricity_dbh=dbh, co2_avoided_dbh=dbh,
                     aq_pm10_dep_dbh=dbh, region="Sim City", aq_voc_avoided_dbh=dbh,
                     aq_pm10_avoided_dbh=dbh, aq_ozone_dep_dbh=dbh, aq_nox_avoided_dbh=dbh,
                     co2_storage_dbh=dbh,aq_sox_avoided_dbh=dbh, aq_sox_dep_dbh=dbh,
                     bvoc_dbh=dbh, co2_sequestered_dbh=dbh, aq_nox_dep_dbh=dbh,
                     hydro_interception_dbh=dbh, natural_gas_dbh=dbh)
    rsrc2 = Resource(meta_species="BDL_OTHER", electricity_dbh=dbh2, co2_avoided_dbh=dbh2,
                    aq_pm10_dep_dbh=dbh2, region="Sim City", aq_voc_avoided_dbh=dbh2,
                    aq_pm10_avoided_dbh=dbh2, aq_ozone_dep_dbh=dbh2, aq_nox_avoided_dbh=dbh2,
                    co2_storage_dbh=dbh2,aq_sox_avoided_dbh=dbh2, aq_sox_dep_dbh=dbh2,
                    bvoc_dbh=dbh2, co2_sequestered_dbh=dbh2, aq_nox_dep_dbh=dbh2,
                    hydro_interception_dbh=dbh2, natural_gas_dbh=dbh2)
    rsrc1.save()
    rsrc2.save()

    u = User.objects.filter(username="jim")

    if u:
        u = u[0]
    else:
        u = User.objects.create_user("jim","jim@test.org","jim")
        u.is_staff = True
        u.is_superuser = True
        u.save()
        up = UserProfile(user=u)
        up.save()
        u.reputation = Reputation(user=u)
        u.reputation.save()

    amy_filter_result = User.objects.filter(username="amy")
    if not amy_filter_result:
        amy = User.objects.create_user("amy","amy@test.org","amy")
    else:
        amy = amy_filter_result[0]
        amy.is_staff = False
        amy.is_superuser = False
        amy.save()
        amy_profile = UserProfile(user=amy)
        amy_profile.save()
        amy.reputation = Reputation(user=amy)
        amy.reputation.save()

    olivia_filter_result = User.objects.filter(username="olivia")
    if not amy_filter_result:
        olivia = User.objects.create_user("olivia","olivia@test.org","olivia")
    else:
        olivia = olivia_filter_result[0]
        olivia.is_staff = False
        olivia.is_superuser = False
        olivia.save()
        olivia_profile = UserProfile(user=olivia)
        olivia_profile.save()
        olivia.reputation = Reputation(user=olivia)
        olivia.reputation.save()

    n1geom = MultiPolygon(Polygon(((0,0),(100,0),(100,100),(0,100),(0,0))))
    n2geom = MultiPolygon(Polygon(((0,101),(101,101),(101,200),(0,200),(0,101))))

    n1 = Neighborhood(name="n1", region_id=2, city="c1", state="PA", county="PAC", geometry=n1geom)
    n2 = Neighborhood(name="n2", region_id=2, city="c2", state="NY", county="NYC", geometry=n2geom)

    n1.save()
    n2.save()

    z1geom = MultiPolygon(Polygon(((0,0),(100,0),(100,100),(0,100),(0,0))))
    z2geom = MultiPolygon(Polygon(((0,100),(100,100),(100,200),(0,200),(0,100))))

    z1 = ZipCode(zip="19107",geometry=z1geom)
    z2 = ZipCode(zip="10001",geometry=z2geom)

    z1.save()
    z2.save()

    exgeom1 = MultiPolygon(Polygon(((0,0),(25,0),(25,25),(0,25),(0,0))))
    ex1 = ExclusionMask(geometry=exgeom1, type="building")

    ex1.save()

    agn1 = AggregateNeighborhood(
        annual_stormwater_management=0.0,
        annual_electricity_conserved=0.0,
        annual_energy_conserved=0.0,
        annual_natural_gas_conserved=0.0,
        annual_air_quality_improvement=0.0,
        annual_co2_sequestered=0.0,
        annual_co2_avoided=0.0,
        annual_co2_reduced=0.0,
        total_co2_stored=0.0,
        annual_ozone=0.0,
        annual_nox=0.0,
        annual_pm10=0.0,
        annual_sox=0.0,
        annual_voc=0.0,
        annual_bvoc=0.0,
        total_trees=0,
        total_plots=0,
        location = n1)

    agn2 = AggregateNeighborhood(
        annual_stormwater_management=0.0,
        annual_electricity_conserved=0.0,
        annual_energy_conserved=0.0,
        annual_natural_gas_conserved=0.0,
        annual_air_quality_improvement=0.0,
        annual_co2_sequestered=0.0,
        annual_co2_avoided=0.0,
        annual_co2_reduced=0.0,
        total_co2_stored=0.0,
        annual_ozone=0.0,
        annual_nox=0.0,
        annual_pm10=0.0,
        annual_sox=0.0,
        annual_voc=0.0,
        annual_bvoc=0.0,
        total_trees=0,
        total_plots=0,
        location = n2)

    agn1.save()
    agn2.save()

    s1 = Species(symbol="s1",genus="testus1",species="specieius1",
                 cultivar_name='',family='',
                 alternate_symbol='a1')
    s2 = Species(symbol="s2",genus="testus2",species="specieius2",
                 cultivar_name='',family='',
                 alternate_symbol='a2')
    s3 = Species(symbol="s3",genus="testus2",species="specieius3",
                 cultivar_name='',family='',
                 alternate_symbol='a3')

    s1.native_status = 'True'
    s1.fall_conspicuous = True
    s1.flower_conspicuous = True
    s1.palatable_human = True

    s2.native_status = 'True'
    s2.fall_conspicuous = False
    s2.flower_conspicuous = True
    s2.palatable_human = False
    s2.wildlife_value = True

    s3.wildlife_value = True

    s1.save()
    s2.save()
    s3.save()

    s1.resource.add(rsrc1)
    s2.resource.add(rsrc2)
    s3.resource.add(rsrc2)

    ie = ImportEvent(file_name='site_add')
    ie.save()

def teardownTreemapEnv():
    for r in APILog.objects.all():
        r.delete()

    for r in APIKey.objects.all():
        r.delete()

    for r in BenefitValues.objects.all():
        r.delete()

    for u in User.objects.all():
        u.delete()

    for r in Neighborhood.objects.all():
        r.delete()

    for r in ZipCode.objects.all():
        r.delete()

    for r in ExclusionMask.objects.all():
        r.delete()

    for r in AggregateNeighborhood.objects.all():
        r.delete()

    for r in Species.objects.all():
        r.delete()

    for r in ImportEvent.objects.all():
        r.delete()

    for r in Tree.objects.all():
        r.delete()

    for r in Plot.objects.all():
        r.delete()

    for r in ReputationAction.objects.all():
        r.delete()

    for r in Resource.objects.all():
        r.delete()

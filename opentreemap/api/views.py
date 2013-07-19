import datetime
from PIL import Image
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.files.base import ContentFile

from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseServerError
from django.shortcuts import get_object_or_404
from django.db import transaction

from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator

from treemap.models import Plot, Species, Tree
from treemap.views import create_user, get_tree_photos, create_plot
from treemap.util import instance_request

from ecobenefits.views import tree_benefits

from treemap.search import create_filter

from treemap.audit import Audit, approve_or_reject_audit_and_apply

from api.models import APIKey, APILog
from django.contrib.gis.geos import Point, fromstr

from api.auth import login_required, create_401unauthorized, login_optional

from functools import wraps

from omgeo import Geocoder
from omgeo.places import PlaceQuery, Viewbox

import json
import struct
import ctypes
import math
import json

from copy import deepcopy

from distutils.version import StrictVersion

#TODO: Kill this
def change_reputation_for_user(*args, **kwargs):
    print "WARNING: Shim called for 'change_reputation_for_user'"


class HttpBadRequestException(Exception):
    pass

class HttpConflictException(Exception):
    pass

class InvalidAPIKeyException(Exception):
    pass

def route(**kwargs):
    @csrf_exempt
    def routed(request, **kwargs2):
        method = request.method
        req_method = kwargs[method]
        return req_method(request, **kwargs2)
    return routed

def json_from_request(request):
    """
    Accessing body throws an exception when using the Django test
    client in to make requests in unit tests.
    """
    try:
        data = json.loads(request.body)
    except Exception, e:
        data = request.POST
    return data

def validate_and_log_api_req(request):
    # Prefer "apikey" in REQUEST, but take either that or the
    # header value
    key = request.META.get("HTTP_X_API_KEY", None)
    key = request.REQUEST.get("apikey", key)

    if key is None:
        raise InvalidAPIKeyException("key not found as 'apikey' param or 'X-API-Key' header")

    apikeys = APIKey.objects.filter(key=key)

    if len(apikeys) > 0:
        apikey = apikeys[0]
    else:
        raise InvalidAPIKeyException("key not found")

    if not apikey.enabled:
        raise InvalidAPIKeyException("key is not enabled")

    # Log the request
    reqstr = ",".join(["%s=%s" % (k,request.REQUEST[k]) for k in request.REQUEST])
    APILog(url=request.get_full_path(),
           remoteip=request.META["REMOTE_ADDR"],
           requestvars=reqstr,
           method=request.method,
           apikey=apikey,
           useragent=request.META.get("HTTP_USER_AGENT",''),
           appver=request.META.get("HTTP_APPLICATIONVERSION",'')
    ).save()

    return apikey


def api_call_raw(content_type="image/jpeg"):
    """ Wrap an API call that writes raw binary data """
    def decorate(req_function):
        @wraps(req_function)
        def newreq(request, *args, **kwargs):
            try:
                validate_and_log_api_req(request)
                outp = req_function(request, *args, **kwargs)
                if issubclass(outp.__class__, HttpResponse):
                    response = outp
                else:
                    response = HttpResponse(outp)

                response['Content-length'] = str(len(response.content))
                response['Content-Type'] = content_type
            except HttpBadRequestException, bad_request:
                response = HttpResponseBadRequest(bad_request.message)

            return response
        return newreq
    return decorate

def api_call(content_type="application/json"):
    """ Wrap an API call that returns an object that
        is convertable from json
    """
    def decorate(req_function):
        @wraps(req_function)
        @csrf_exempt
        def newreq(request, *args, **kwargs):
            try:
                validate_and_log_api_req(request)
                outp = req_function(request, *args, **kwargs)
                if issubclass(outp.__class__, HttpResponse):
                    response = outp
                else:
                    response = HttpResponse()
                    response.write('%s' % json.dumps(outp))
                    response['Content-length'] = str(len(response.content))
                    response['Content-Type'] = content_type

            except HttpBadRequestException, bad_request:
                response = HttpResponseBadRequest(bad_request.message)

            except HttpConflictException, conflict:
                response = HttpResponse(conflict.message)
                response.status_code = 409

            return response

        return newreq
    return decorate

def datetime_to_iso_string(d):
    if d:
        return d.strftime('%Y-%m-%d %H:%M:%S')
    else:
        return None

def plot_permissions(plot, user):
    ####TODO- Totally broke
    perms = { "plot": plot_or_tree_permissions(plot, user) }

    tree = plot.current_tree()
    if tree:
        perms["tree"] = plot_or_tree_permissions(tree, user)

    return perms

def plot_or_tree_permissions(obj, user):
    ####TODO- Totally broke
    """ Determine what the given user can do with a tree or plot
        Returns {
           can_delete: <boolean>,
           can_edit: <boolean>,
        } """

    can_delete = False
    can_edit = False

    # If user is none or anonymous, they can't do anything
    if not user or user.is_anonymous():
        can_delete = False
        can_edit = False
    # If an object is readonly, it can never be deleted or edited
    elif obj.readonly:
        can_delete = False
        can_edit = False
    # If the user is an admin they can do whatever they want
    # (but not to readonly trees)
    elif user.has_perm('auth.change_user'):
        can_delete = True
        can_edit = True
    else:
        # If the user is the owner of the object
        # they can do whatever
        creator = obj.created_by
        if creator and creator.pk == user.pk:
            can_delete = True
            can_edit = True
        # If the tree is not readonly, and the user isn't an admin
        # and the user doesn't own the objet, editing is allowed
        # but delete is not
        else:
            can_delete = False
            can_edit = True

    return { "can_delete": can_delete, "can_edit": can_edit }

def can_delete_tree_or_plot(obj, user):
    permissions = plot_or_tree_permissions(obj, user)
    if "can_delete" in permissions:
        return permissions["can_delete"]
    else:
        # This should never happen, but raising an exception ensures that it will fail loudly if a
        # future refactoring introduces a bug.
        raise Exception("Expected the dict returned from plot_or_tree_permissions to contain 'can_delete'")


@require_http_methods(["GET"])
@api_call()
def status(request):
    return [{'api_version': 'v2',
             'status': 'online',
             'message': ''}]


@require_http_methods(["GET"])
@api_call()
@login_required
def verify_auth(request):
    user_dict = user_to_dict(request.user)
    user_dict["status"] = "success"
    return user_dict

@require_http_methods(["POST"])
@api_call()
@transaction.commit_on_success
def register(request):
    data = json.loads(request.body)

    user = create_user(**data)

    return { "status": "success", "id": user.pk }

@require_http_methods(["POST"])
@api_call()
@login_required
def add_tree_photo(request, plot_id):
    content_type = request.META.get('CONTENT_TYPE')
    if not content_type:
        content_type = "image/png" # Older versions of the iOS client sent PNGs exclusively
    file_type = content_type.lower().split('/')[-1]
    uploaded_image = ContentFile(request.body)
    uploaded_image.name = "plot_%s.%s" % (plot_id, file_type)

    treephoto = add_tree_photo(request.user.pk, plot_id, uploaded_image)

    return { "status": "success", "title": treephoto.title, "id": treephoto.pk }


@require_http_methods(["POST"])
@api_call()
@login_required
def add_profile_photo(request, user_id, title):
    uploaded_image = ContentFile(request.body)
    uploaded_image.name = "%s.png" % title

    add_user_photo(user_id, uploaded_image)

    return { "status": "success" }

def extract_plot_from_audit(audit):
    if audit.model == 'Plot':
        return Plot.objects.get(pk=audit.model_id)
    elif audit.model == 'Tree':
        return Tree.objects.get(id=audit.model_id).plot

@require_http_methods(["GET"])
@api_call()
@instance_request
@login_required
def recent_edits(request, instance, user_id):
    if (int(user_id) != request.user.pk):
        return create_401unauthorized()

    user = User.objects.get(pk=user_id)

    result_offset = int(request.REQUEST.get("offset",0))
    num_results = min(int(request.REQUEST.get("length",15)),15)

    audits = Audit.objects.filter(instance=instance)\
                          .filter(user=user)\
                          .filter(model_in=['Tree', 'Plot'])\
                          .order_by('-created', 'id')

    audits = audits[result_offset:(result_offset+num_results)]

    keys = []
    for audit in audits:
        d = {}
        plot = extract_plot_from_audit(act)
        d["plot_id"] = plot_id

        if plot_id:
            d["plot"] = plot_to_dict(
                plot, longform=true, user=user)

        d["id"] = audit.pk
        d["name"] = audit.display_action
        d["created"] = datetime_to_iso_string(audit.created)
        d["value"] = audit.current_value

        keys.append(d)

    return keys


@require_http_methods(["PUT"])
@api_call()
@login_required
def update_password(request, user_id):
    data = json.loads(request.body)

    pw = data["password"]

    user = User.objects.get(pk=user_id)

    user.set_password(pw)
    user.save()

    return { "status": "success" }


@require_http_methods(["POST"])
@api_call()
def reset_password(request):
    resetform = PasswordResetForm({ "email" : request.REQUEST["email"]})

    if (resetform.is_valid()):
        opts = {
            'use_https': request.is_secure(),
            'token_generator': default_token_generator,
            'from_email': None,
            'email_template_name': 'reset_email_password.html',
            'request': request,
            }

        resetform.save(**opts)
        return { "status": "success" }
    else:
        raise HttpBadRequestException()

@require_http_methods(["GET"])
@api_call()
def version(request):
    """ API Request

    Get version information for OTM and the API. Generally, the API is unstable for
    any API version < 1 and minor changes (i.e. 1.4,1.5,1.6) represent no break in
    existing functionality

    Verb: GET
    Params: None
    Output:
      {
        otm_version, string -> Open Tree Map Version (i.e. 1.0.2)
        api_version, string -> API version (i.e. 1.6)
      }

    """
    return { "otm_version": settings.OTM_VERSION,
             "api_version": settings.API_VERSION }

@require_http_methods(["GET"])
@api_call_raw("image/png")
def get_tree_image(request, plot_id, photo_id):
    """ API Request

    Verb: GET
    Params:

    Output:
      image/jpeg raw data
    """
    img = get_tree_photos(plot_id, photo_id)

    if img:
        resized = img.resize((144,132), Image.ANTIALIAS)
        response = HttpResponse(mimetype="image/png")
        resized.save(response, "PNG")
        return response
    else:
        raise HttpBadRequestException('invalid url (missing objects)')

@require_http_methods(["GET"])
@api_call()
def get_plot_list(request):
    """ API Request

    Get a list of all plots in the database. This is meant to be a lightweight
    listing service. To get more details about a plot use the ^plot/{id}$ service

    Verb: GET
    Params:
      offset, integer, default = 0  -> offset to start results from
      size, integer, default = 100 -> Maximum 10000, number of results to get

    Output:
      [{
          width, integer, opt -> Width of tree bed
          length, integer, opt -> Length of bed
          type, string, opt -> Plot type
          geometry, Point -> Lat/lng pt
          readonly, boolean -> True if this is a readonly tree
          tree, {
             id, integer -> tree id
             species, integer, opt -> Species id
             dbh, real, opt -> Diameter of the tree
          }
       }]

      """
    start = int(request.REQUEST.get("offset","0"))
    size = min(int(request.REQUEST.get("size", "100")), 10000)
    end = size + start

    # order_by prevents testing weirdness
    plots = Plot.objects.filter(present=True).order_by('id')[start:end]

    return [convert_response_plot_dict_choice_values(request, plot) for plot in plots_to_list_of_dict(plots,user=request.user)]

@require_http_methods(["GET"])
@api_call()
def species_list(request, lat=None, lon=None):
    allspecies = Species.objects.all()

    return [species_to_dict(z) for z in allspecies]

@require_http_methods(["GET"])
@api_call()
@login_optional
def plots_closest_to_point(request, lat=None, lon=None):
    point = Point(float(lon), float(lat), srid=4326)

    distance_string = request.GET.get('distance', settings.MAP_CLICK_RADIUS)
    try:
        distance = float(distance_string)
    except ValueError:
        raise HttpBadRequestException('The distance parameter must be a number')

    max_plots_string = request.GET.get('max_plots', '1')
    try:
        max_plots = int(max_plots_string)
    except ValueError:
        raise HttpBadRequestException('The max_plots parameter must be a number between 1 and 500')

    if max_plots > 500 or max_plots < 1:
        raise HttpBadRequestException('The max_plots parameter must be a number between 1 and 500')

    species = request.GET.get('species', None)

    sort_recent = request.GET.get('filter_recent', None)
    if sort_recent and sort_recent == "true":
        sort_recent = True
    else:
        sort_recent = False

    sort_pending = request.GET.get('filter_pending', None)
    if sort_pending and sort_pending == "true":
        sort_pending = True
    else:
        sort_pending = False

    has_tree = request.GET.get("has_tree",None)
    if has_tree:
        if has_tree == "true":
            has_tree = True
        else:
            has_tree = False

    has_species = request.GET.get("has_species",None)
    if has_species:
        if has_species == "true":
            has_species = True
        else:
            has_species = False

    has_dbh = request.GET.get("has_dbh",None)
    if has_dbh:
        if has_dbh == "true":
            has_dbh = True
        else:
            has_dbh = False

    plots, extent = Plot.locate.with_geometry(
        point, distance, max_plots, species,
        native=str2bool(request.GET,"filter_native"),
        flowering=str2bool(request.GET,'filter_flowering'),
        fall=str2bool(request.GET,'filter_fall_colors'),
        edible=str2bool(request.GET,'filter_edible'),
        dbhmin=request.GET.get("filter_dbh_min",None),
        dbhmax=request.GET.get("filter_dbh_max",None),
        species=request.GET.get("filter_species",None),
        pests=request.GET.get("filter_pests",None),
        sort_recent=sort_recent, sort_pending=sort_pending,
        has_tree=has_tree, has_species=has_species, has_dbh=has_dbh)

    return [convert_response_plot_dict_choice_values(request, plot) for plot in plots_to_list_of_dict(plots, longform=True, user=request.user)]

def str2bool(ahash, akey):
    if akey in ahash:
        return ahash[akey] == "true"
    else:
        return None

def plots_to_list_of_dict(plots,longform=False,user=None):
    return [plot_to_dict(plot,longform=longform,user=user) for plot in plots]

def point_wkt_to_dict(wkt):
    point = fromstr(wkt)
    return {
        'lat': point.y,
        'lng': point.x,
        'srid': '4326'
    }

def pending_edit_to_dict(pending_edit):
    if pending_edit.field == 'geometry':
        pending_value = point_wkt_to_dict(pending_edit.value) # Pending geometry edits are stored as WKT
    else:
        pending_value = pending_edit.value

    return {
        'id': pending_edit.pk,
        'submitted': datetime_to_iso_string(pending_edit.submitted),
        'value': pending_value,
        'username': pending_edit.submitted_by.username
    }

def plot_to_dict(plot,longform=False,user=None):
    pending_edit_dict = {} #If settings.PENDING_ON then this will be populated and included in the response
    current_tree = plot.current_tree()
    if current_tree:
        tree_dict = { "id" : current_tree.pk }

        if current_tree.species:
            tree_dict["species"] = current_tree.species.pk
            tree_dict["species_name"] = current_tree.species.common_name
            tree_dict["sci_name"] = current_tree.get_scientific_name()

        if current_tree.dbh:
            tree_dict["dbh"] = current_tree.dbh

        if current_tree.height:
            tree_dict["height"] = current_tree.height

        if current_tree.canopy_height:
            tree_dict["canopy_height"] = current_tree.canopy_height

        images = current_tree.treephoto_set.all()

        if len(images) > 0:
            tree_dict["images"] = [{"id": image.pk, "title": image.title, "url": image.photo.url}
                                   for image in images]

        if longform:
            tree_dict['tree_owner'] = current_tree.tree_owner
            tree_dict['steward_name'] = current_tree.steward_name
            tree_dict['sponsor'] = current_tree.sponsor

            if len(TreeResource.objects.filter(tree=current_tree)) > 0:
                tree_dict['eco'] = tree_resource_to_dict(current_tree.treeresource)

            if current_tree.steward_user:
                tree_dict['steward_user'] = current_tree.steward_user

            tree_dict['species_other1'] = current_tree.species_other1
            tree_dict['species_other2'] = current_tree.species_other2
            tree_dict['date_planted'] = datetime_to_iso_string(current_tree.date_planted)
            tree_dict['date_removed'] = datetime_to_iso_string(current_tree.date_removed)
            tree_dict['present'] = current_tree.present
            tree_dict['last_updated'] = datetime_to_iso_string(current_tree.last_updated)
            tree_dict['last_updated_by'] = current_tree.last_updated_by.username
            tree_dict['condition'] = current_tree.condition
            tree_dict['canopy_condition'] = current_tree.canopy_condition
            tree_dict['pests'] = current_tree.pests
            tree_dict['readonly'] = current_tree.readonly

            if settings.PENDING_ON:
                tree_field_reverse_property_name_dict = {'species_id': 'species'}
                for raw_field_name, detail in current_tree.get_active_pend_dictionary().items():
                    if raw_field_name in tree_field_reverse_property_name_dict:
                        field_name = tree_field_reverse_property_name_dict[raw_field_name]
                    else:
                        field_name = raw_field_name
                    pending_edit_dict['tree.' + field_name] = {'latest_value': detail['latest_value'], 'pending_edits': []}
                    for pend in detail['pending_edits']:
                        pend_dict = pending_edit_to_dict(pend)
                        if field_name == 'species':
                            species_set = Species.objects.filter(pk=pend_dict['value'])
                            if species_set:
                                pend_dict['related_fields'] = {
                                    'tree.sci_name': species_set[0].scientific_name,
                                    'tree.species_name': species_set[0].common_name
                                }
                        pending_edit_dict['tree.' + field_name]['pending_edits'].append(pend_dict)

    else:
        tree_dict = None

    base = {
        "id": plot.pk,
        "plot_width": plot.width,
        "plot_length": plot.length,
        "owner_orig_id": plot.owner_orig_id,
        "plot_type": plot.type,
        "readonly": plot.readonly,
        "tree": tree_dict,
        "address": plot.geocoded_address,
        "geometry": {
            "srid": plot.geometry.srid,
            "lat": plot.geometry.y,
            "lng": plot.geometry.x
        }
    }

    if user:
        base["perm"] = plot_permissions(plot,user)

    if longform:
        base['power_lines'] = plot.powerline_conflict_potential
        base['sidewalk_damage'] = plot.sidewalk_damage
        base['address_street'] = plot.address_street
        base['address_city'] = plot.address_city
        base['address_zip'] = plot.address_zip

        if plot.data_owner:
            base['data_owner'] = plot.data_owner.pk

        base['last_updated'] = datetime_to_iso_string(plot.last_updated)

        if plot.last_updated_by:
            base['last_updated_by'] = plot.last_updated_by.username

        if settings.PENDING_ON:
            plot_field_reverse_property_name_dict = {'width': 'plot_width', 'length': 'plot_length', 'powerline_conflict_potential': 'power_lines'}

            for raw_field_name, detail in plot.get_active_pend_dictionary().items():
                if raw_field_name in plot_field_reverse_property_name_dict:
                    field_name = plot_field_reverse_property_name_dict[raw_field_name]
                else:
                    field_name = raw_field_name

                if field_name == 'geometry':
                    latest_value = point_wkt_to_dict(detail['latest_value'])
                else:
                    latest_value = detail['latest_value']

                pending_edit_dict[field_name] = {'latest_value': latest_value, 'pending_edits': []}
                for pend in detail['pending_edits']:
                    pending_edit_dict[field_name]['pending_edits'].append(pending_edit_to_dict(pend))
            base['pending_edits'] = pending_edit_dict

    return base


def convert_response_plot_dict_choice_values(request, plot_dict):
    return convert_plot_dict_choice_values(request, plot_dict, 'reverse')


def convert_request_plot_dict_choice_values(request, plot_dict):
    return convert_plot_dict_choice_values(request, plot_dict, 'forward')


def convert_plot_dict_choice_values(request, plot_dict, direction):
    if direction not in ['forward', 'reverse']:
        raise ValueError('direction argument must be "forward" or "reverse"')

    # If no conversions are defined, bail out quickly since no work has to be done
    if not hasattr(settings, 'CHOICE_CONVERSIONS'):
        return plot_dict

    # The list of attributes that are nested under the 'tree' key in the plot dict
    TREE_ATTRS = ['condition', 'canopy_condition']
    # A map from the Django model atrributes to serialized attribute names
    ATTR_TO_KEY = {
        'powerline_conflict_potential': 'power_lines'
    }

    converted_plot_dict = deepcopy(plot_dict)

    for attr in [x for x in settings.CHOICE_CONVERSIONS.keys() if _attribute_requires_conversion(request, x)]:
        if attr in ATTR_TO_KEY.keys():
            dict_key = ATTR_TO_KEY[attr]
        else:
            dict_key = attr

        conversions = settings.CHOICE_CONVERSIONS[attr][direction]

        def do_conversion(value):
            if value is not None:
                for (a, b) in conversions:
                    if str(value) == str(a):
                        value = b
                        break
            return value

        # Regular fields
        if attr in TREE_ATTRS:
            if 'tree' in converted_plot_dict and converted_plot_dict['tree'] is not None:
                value = do_conversion(converted_plot_dict['tree'].get(dict_key, None))
            else:
                value = None
        else:
            value = do_conversion(converted_plot_dict.get(dict_key, None))

        if value is not None:
            if attr in TREE_ATTRS:
                converted_plot_dict['tree'][dict_key] = value
            else:
                converted_plot_dict[dict_key] = value

        # Pending edits
        if 'pending_edits' in converted_plot_dict:
            if attr in TREE_ATTRS:
                pend_key = 'tree.' + dict_key
            else:
                pend_key = dict_key

            pend_field_dict = converted_plot_dict['pending_edits'].get(pend_key, None)
            if pend_field_dict is not None:
                # Update the latest value
                value = do_conversion(pend_field_dict.get('latest_value', None))
                if value is not None:
                    pend_field_dict['latest_value'] = value

                # Update each pending value
                pend_values_dicts = pend_field_dict.get('pending_edits', None)
                if pend_values_dicts is not None:
                    for pend_value_dict in pend_values_dicts:
                        value = do_conversion(pend_value_dict.get('value', None))
                        if value is not None:
                            pend_value_dict['value'] = value

    return converted_plot_dict


def tree_resource_to_dict(tr):
    b = BenefitValues.objects.all()[0]

    ac_dollar = tr.annual_ozone * b.ozone + tr.annual_nox * b.nox + \
                tr.annual_pm10 * b.pm10 + tr.annual_sox * b.sox + \
                tr.annual_voc * b.voc + tr.annual_bvoc * b.bvoc

    weight_unit = getattr(settings, 'ECO_WEIGHT_UNIT', 'lbs')
    elec_unit = getattr(settings, 'ECO_POWER_UNIT', 'kWh')
    water_unit = getattr(settings, 'ECO_WATER_UNIT', 'gallons')

    return {
        "annual_stormwater_management": with_unit(tr.annual_stormwater_management, b.stormwater, water_unit),
        "annual_electricity_conserved": with_unit(tr.annual_electricity_conserved, b.electricity, elec_unit),
        "annual_energy_conserved": with_unit(tr.annual_energy_conserved, b.electricity, elec_unit),
        "annual_natural_gas_conserved": with_unit(tr.annual_natural_gas_conserved, b.electricity, elec_unit),
        "annual_air_quality_improvement": with_unit(tr.annual_air_quality_improvement, None, weight_unit, dollar=ac_dollar),
        "annual_co2_sequestered": with_unit(tr.annual_co2_sequestered, b.co2, weight_unit),
        "annual_co2_avoided": with_unit(tr.annual_co2_avoided, b.co2, weight_unit),
        "annual_co2_reduced": with_unit(tr.annual_co2_reduced, b.co2, weight_unit),
        "total_co2_stored": with_unit(tr.total_co2_stored, b.co2, weight_unit),
        "annual_ozone": with_unit(tr.annual_ozone, b.ozone, weight_unit),
        "annual_nox": with_unit(tr.annual_nox, b.nox, weight_unit),
        "annual_pm10": with_unit(tr.annual_pm10, b.pm10,  weight_unit),
        "annual_sox": with_unit(tr.annual_sox, b.sox, weight_unit),
        "annual_voc": with_unit(tr.annual_voc, b.voc, weight_unit),
        "annual_bvoc": with_unit(tr.annual_bvoc, b.bvoc, weight_unit) }

def with_unit(val,dollar_factor,unit,dollar=None):
    if dollar is None:
        dollar = dollar_factor * val

    return { "value": val, "unit": unit, "dollars": dollar }


def species_to_dict(s):
    return {
        "id": s.pk,
        "scientific_name": s.scientific_name,
        "genus": s.genus,
        "species": s.species,
        "cultivar": s.cultivar_name,
        "gender": s.gender,
        "common_name": s.common_name }


def user_to_dict(user):
    return {
        "id": user.pk,
        "firstname": user.first_name,
        "lastname": user.last_name,
        "email": user.email,
        "username": user.username,
        "zipcode": UserProfile.objects.get(user__pk=user.pk).zip_code,
        "reputation": Reputation.objects.reputation_for_user(user).reputation,
        "permissions": list(user.get_all_permissions()),
        "user_type": user_access_type(user)
        }

def user_access_type(user):
    """ Given a user, determine the name and "level" of a user """
    if user.is_superuser:
        return { 'name': 'administrator', 'level': 1000 }
    elif Reputation.objects.reputation_for_user(user).reputation > 1000:
        return { 'name': 'editor', 'level': 500 }
    else:
        return { 'name': 'public', 'level': 0 }


@require_http_methods(["GET"])
@api_call()
def geocode_address(request, address):
    def result_in_bounding_box(result):
        x = float(result.x)
        y = float(result.y)
        left = float(settings.BOUNDING_BOX['left'])
        top = float(settings.BOUNDING_BOX['top'])
        right = float(settings.BOUNDING_BOX['right'])
        bottom = float(settings.BOUNDING_BOX['bottom'])
        return x > left and x < right and y > bottom and y < top

    if address is None or len(address) == 0:
        raise HttpBadRequestException("No address specfified")

    query = PlaceQuery(address, viewbox=Viewbox(
        settings.BOUNDING_BOX['left'],
        settings.BOUNDING_BOX['top'],
        settings.BOUNDING_BOX['right'],
        settings.BOUNDING_BOX['bottom'])
    )

    if 'OMGEO_GEOCODER_SOURCES' in dir(settings) and settings.OMGEO_GEOCODER_SOURCES is not None:
        geocoder = Geocoder(settings.OMGEO_GEOCODER_SOURCES)
    else:
        geocoder = Geocoder()

    results = geocoder.geocode(query)
    if results != False:
        response = []
        for result in results:
            if result_in_bounding_box(result): # some geocoders do not support passing a bounding box filter
                response.append({
                     "match_addr": result.match_addr,
                     "x": result.x,
                     "y": result.y,
                     "score": result.score,
                     "locator": result.locator,
                     "geoservice": result.geoservice,
                     "wkid": result.wkid,
                })
        return response
    else:
        # This is not a very helpful error message, but omgeo as of v1.2 does not
        # report failure details.
        return {"error": "The geocoder failed to generate a list of results."}

def flatten_plot_dict_with_tree_and_geometry(plot_dict):
    if 'tree' in plot_dict and plot_dict['tree'] is not None:
        tree_dict = plot_dict['tree']
        for field_name in tree_dict.keys():
            plot_dict[field_name] = tree_dict[field_name]
        del plot_dict['tree']
    if 'geometry' in plot_dict:
        geometry_dict = plot_dict['geometry']
        for field_name in geometry_dict.keys():
            plot_dict[field_name] = geometry_dict[field_name]
        del plot_dict['geometry']

def rename_plot_request_dict_fields(request_dict):
    '''
    The new plot/tree form requires specific field names that do not directly match
    up with the model objects (e.g. the form expects a 'species_id' field) so this
    helper function renames keys in the dictionary to match what the form expects
    '''
    field_map = {'species': 'species_id', 'width': 'plot_width', 'length': 'plot_length'}
    for map_key in field_map.keys():
        if map_key in request_dict:
            request_dict[field_map[map_key]] = request_dict[map_key]
            del request_dict[map_key]
    return request_dict

@require_http_methods(["POST"])
@api_call()
@login_required
def create_plot_optional_tree(request):
    response = HttpResponse()

    # Unit tests fail to access request.body
    request_dict = json_from_request(request)

    # Convert any 'legacy' choice values
    request_dict = convert_request_plot_dict_choice_values(request, request_dict)

    # The Django form used to validate and save plot and tree information expects
    # a flat dictionary. Allowing the tree and geometry details to be in nested
    # dictionaries in API calls clarifies, to API clients, the distinction between
    # Plot and Tree and groups the coordinates along with their spatial reference
    flatten_plot_dict_with_tree_and_geometry(request_dict)

    # The new plot/tree form requires specific field names that do not directly match
    # up with the model objects (e.g. the form expects a 'species_id' field) so this
    # helper function renames keys in the dictionary to match what the form expects
    rename_plot_request_dict_fields(request_dict)

    form = TreeAddForm(request_dict, request.FILES)

    if not form.is_valid():
        response.status_code = 400
        if '__all__' in form.errors:
            response.content = simplejson.dumps({"error": form.errors['__all__']})
        else:
            response.content = simplejson.dumps({"error": form.errors})
        return response

    try:
        new_plot = form.save(request)
    except ValidationError, ve:
        response.status_code = 400
        response.content = simplejson.dumps({"error": form.error_class(ve.messages)})
        return response

    new_tree = new_plot.current_tree()
    if new_tree:
        change_reputation_for_user(request.user, 'add tree', new_tree)
    else:
        change_reputation_for_user(request.user, 'add plot', new_plot)

    response.status_code = 201
    new_plot = convert_response_plot_dict_choice_values(request, plot_to_dict(Plot.objects.get(pk=new_plot.id),longform=True,user=request.user))
    response.content = json.dumps(new_plot)
    return response

@require_http_methods(["GET"])
@api_call()
@login_optional
def get_plot(request, plot_id):
    return convert_response_plot_dict_choice_values(request,
        plot_to_dict(Plot.objects.get(pk=plot_id), longform=True, user=request.user)
    )

def compare_fields(v1,v2):
    if v1 is None:
        return v1 == v2
    try:
        v1f = float(v1)
        v2f = float(v2)
        return v1f == v2f
    except ValueError:
        return v1 == v2


def _parse_application_version_header_as_dict(request):
    if request is None:
        return None

    app_version = {
        'platform': 'UNKNOWN',
        'version': 'UNKNOWN',
        'build': 'UNKNOWN'
    }

    version_string = request.META.get("HTTP_APPLICATIONVERSION", '')
    if version_string == '':
        return app_version

    segments = version_string.rsplit('-')
    if len(segments) >= 1:
        app_version['platform'] = segments[0]
    if len(segments) >= 2:
        app_version['version'] = segments[1]
    if len(segments) >= 3:
        app_version['build'] = segments[2]

    return app_version


def _attribute_requires_conversion(request, attr):
    if attr is None:
        return False

    if not hasattr(settings, 'CHOICE_CONVERSIONS'):
        # If CHOICE_CONVERSIONS is not defined in settings then
        # no conversion is required
        return False

    if attr in settings.CHOICE_CONVERSIONS:
        conversion = settings.CHOICE_CONVERSIONS[attr]
        app_version = _parse_application_version_header_as_dict(request)
        if 'version-threshold' in conversion \
        and app_version['platform'] in conversion['version-threshold']:
            threshold_string = conversion['version-threshold'][app_version['platform']]
            # If the threshold is not parsable as a version number, we want this method
            # to crash hard. The CHOICE_CONVERSIONS are misconfigured.
            threshold = StrictVersion(threshold_string)

            try:
                version = StrictVersion(app_version['version'])
            except ValueError:
                # If the version number reported from the app is not parsable as a
                # version number then we assume the app is an old version and that we do
                # need to convert the values.
                return True

            return version < threshold
        else:
            # If a version threshold is not defined for the platform specified in the
            # ApplicationVersion header or the ApplicationVersion header is missing
            # or does not match anything
            return True
    else:
        # If the settings.CHOICE_CONVERSIONS hash does not contain the attribute name
        # then no conversion is required
        return False


@require_http_methods(["PUT"])
@api_call()
@login_required
def update_plot_and_tree(request, plot_id):

    def set_attr_with_choice_correction(request, model, attr, value):
        if _attribute_requires_conversion(request, attr):
            conversions = settings.CHOICE_CONVERSIONS[attr]['forward']
            for (old, new) in conversions:
                if str(value) == str(old):
                    value = new
                    break
        setattr(model, attr, value)

    def get_attr_with_choice_correction(request, model, attr):
        value = getattr(model, attr)
        if _attribute_requires_conversion(request, attr):
            conversions = settings.CHOICE_CONVERSIONS[attr]['reverse']
            for (new, old) in conversions:
                if str(value) == str(new):
                    value = old
                    break
        return value

    response = HttpResponse()
    try:
        plot = Plot.objects.get(pk=plot_id)
    except Plot.DoesNotExist:
        response.status_code = 400
        response.content = json.dumps({"error": "No plot with id %s" % plot_id})
        return response

    request_dict = convert_request_plot_dict_choice_values(request, json_from_request(request))

    flatten_plot_dict_with_tree_and_geometry(request_dict)

    plot_field_whitelist = ['plot_width','plot_length','type','geocoded_address','edit_address_street', 'address_city', 'address_street', 'address_zip', 'power_lines', 'sidewalk_damage']

    # The Django form that creates new plots expects a 'plot_width' parameter but the
    # Plot model has a 'width' parameter so this dict acts as a translator between request
    # keys and model field names
    plot_field_property_name_dict = {'plot_width': 'width', 'plot_length': 'length', 'power_lines': 'powerline_conflict_potential'}

    should_create_plot_pends = requires_pending_record(plot, request.user)

    plot_was_edited = False
    for plot_field_name in request_dict.keys():
        if plot_field_name in plot_field_whitelist:
            if plot_field_name in plot_field_property_name_dict:
                new_name = plot_field_property_name_dict[plot_field_name]
            else:
                new_name = plot_field_name
            new_value = request_dict[plot_field_name]
            if not compare_fields(get_attr_with_choice_correction(request, plot, new_name), new_value):
                if should_create_plot_pends:
                    plot_pend = PlotPending(plot=plot)
                    plot_pend.set_create_attributes(request.user, new_name, new_value)
                    plot_pend.save()
                else:
                    set_attr_with_choice_correction(request, plot, new_name, new_value)
                    plot_was_edited = True

    # TODO: Standardize on lon or lng
    if 'lat' in request_dict or 'lon' in request_dict or 'lng' in request_dict:
        new_geometry = Point(x=plot.geometry.x, y=plot.geometry.y)
        if 'lat' in request_dict:
            new_geometry.y = request_dict['lat']
        if 'lng' in request_dict:
            new_geometry.x = request_dict['lng']
        if 'lon' in request_dict:
            new_geometry.x = request_dict['lon']

        if plot.geometry.x != new_geometry.x or plot.geometry.y != new_geometry.y:
            if should_create_plot_pends:
                plot_pend = PlotPending(plot=plot)
                plot_pend.set_create_attributes(request.user, 'geometry', new_geometry)
                plot_pend.save()
            else:
                plot.geometry = new_geometry
                plot_was_edited = True

    if plot_was_edited:
        plot.last_updated = datetime.datetime.now()
        plot.last_updated_by = request.user
        plot.save()
        change_reputation_for_user(request.user, 'edit plot', plot)

    tree_was_edited = False
    tree_was_added = False
    tree = plot.current_tree()
    tree_field_whitelist = ['species','dbh','height','canopy_height', 'canopy_condition', 'condition','pests']

    if tree is None:
        should_create_tree_pends = False
    else:
        should_create_tree_pends = requires_pending_record(tree, request.user)

    for tree_field in Tree._meta.fields:
        if tree_field.name in request_dict and tree_field.name in tree_field_whitelist:
            if tree is None:
                import_event, created = ImportEvent.objects.get_or_create(file_name='site_add',)
                tree = Tree(plot=plot, last_updated_by=request.user, import_event=import_event)
                tree.plot = plot
                tree.last_updated_by = request.user
                tree.save()
                tree_was_added = True
            if tree_field.name == 'species':
                try:
                    if (tree.species and tree.species.pk != request_dict[tree_field.name]) \
                    or (not tree.species and request_dict[tree_field.name]):
                        if should_create_tree_pends:
                            tree_pend = TreePending(tree=tree)
                            tree_pend.set_create_attributes(request.user, 'species_id', request_dict[tree_field.name])
                            tree_pend.save()
                        else:
                            tree.species = Species.objects.get(pk=request_dict[tree_field.name])
                            tree_was_edited = True
                except Exception:
                    response.status_code = 400
                    response.content = json.dumps({"error": "No species with id %s" % request_dict[tree_field.name]})
                    return response
            else: # tree_field.name != 'species'
                if not compare_fields(get_attr_with_choice_correction(request, tree, tree_field.name), request_dict[tree_field.name]):
                    if should_create_tree_pends:
                        tree_pend = TreePending(tree=tree)
                        tree_pend.set_create_attributes(request.user, tree_field.name, request_dict[tree_field.name])
                        tree_pend.save()
                    else:
                        set_attr_with_choice_correction(request, tree, tree_field.name, request_dict[tree_field.name])
                        tree_was_edited = True

    if tree_was_edited:
        tree.last_updated = datetime.datetime.now()
        tree.last_updated_by = request.user

    if tree_was_added or tree_was_edited:
        tree.save()

    # You cannot get reputation for both adding and editing a tree in one action
    # so I use an elif here
    if tree_was_added:
        change_reputation_for_user(request.user, 'add tree', tree)
    elif tree_was_edited:
        change_reputation_for_user(request.user, 'edit tree', tree)

    full_plot = Plot.objects.get(pk=plot.id)
    return_dict = convert_response_plot_dict_choice_values(request, plot_to_dict(full_plot, longform=True,user=request.user))
    response.status_code = 200
    response.content = json.dumps(return_dict)
    return response

@require_http_methods(["POST"])
@api_call()
@login_required
@has_pending_permission_or_403_forbidden
def approve_pending_edit(request, pending_edit_id):
    pend, model = get_tree_pend_or_plot_pend_by_id_or_404_not_found(pending_edit_id)

    pend.approve_and_reject_other_active_pends_for_the_same_field(request.user)

    if model == 'Tree':
        change_reputation_for_user(pend.submitted_by, 'edit tree', pend.tree, change_initiated_by_user=pend.updated_by)
        updated_plot = Plot.objects.get(pk=pend.tree.plot.id)
    else: # model == 'Plot'
        change_reputation_for_user(pend.submitted_by, 'edit plot', pend.plot, change_initiated_by_user=pend.updated_by)
        updated_plot = Plot.objects.get(pk=pend.plot.id)

    return convert_response_plot_dict_choice_values(request, plot_to_dict(updated_plot, longform=True))

@require_http_methods(["POST"])
@api_call()
@login_required
@has_pending_permission_or_403_forbidden
def reject_pending_edit(request, pending_edit_id):
    pend, model = get_tree_pend_or_plot_pend_by_id_or_404_not_found(pending_edit_id)
    pend.reject(request.user)
    if model == 'Tree':
        updated_plot = Plot.objects.get(pk=pend.tree.plot.id)
    else: # model == 'Plot'
        updated_plot = Plot.objects.get(pk=pend.plot.id)
    return convert_response_plot_dict_choice_values(request, plot_to_dict(updated_plot, longform=True))


@require_http_methods(["DELETE"])
@api_call()
@login_required
@transaction.commit_on_success
def remove_plot(request, plot_id):
    plot = get_object_or_404(Plot, pk=plot_id)
    if can_delete_tree_or_plot(plot, request.user):
        plot.remove()
        return {"ok": True}
    else:
        raise PermissionDenied('%s does not have permission to delete plot %s' % (request.user.username, plot_id))

@require_http_methods(["DELETE"])
@api_call()
@login_required
@transaction.commit_on_success
def remove_current_tree_from_plot(request, plot_id):
    plot = get_object_or_404(Plot, pk=plot_id)
    tree = plot.current_tree()
    if tree:
        if can_delete_tree_or_plot(tree, request.user):
            tree.remove()
            updated_plot = Plot.objects.get(pk=plot_id)
            return convert_response_plot_dict_choice_values(request, plot_to_dict(updated_plot, longform=True, user=request.user))
        else:
            raise PermissionDenied('%s does not have permission to the current tree from plot %s' % (request.user.username, plot_id))
    else:
        raise HttpResponseBadRequest("Plot %s does not have a current tree" % plot_id)

@require_http_methods(["GET"])
@api_call()
def get_current_tree_from_plot(request, plot_id):
    plot = get_object_or_404(Plot, pk=plot_id)
    if  plot.current_tree():
        plot_dict = convert_response_plot_dict_choice_values(request,
            plot_to_dict(plot, longform=True)
        )
        return plot_dict['tree']
    else:
        raise HttpResponseBadRequest(
            "Plot %s does not have a current tree" % plot_id)

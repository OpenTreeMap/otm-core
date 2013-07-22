from PIL import Image
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile

from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.db import transaction, IntegrityError

from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User

from django.contrib.gis.measure import D
from django.contrib.auth.tokens import default_token_generator

from treemap.models import Plot, Species, Tree, Instance
from treemap.views import (create_user, get_tree_photos, create_plot,
                           add_user_photo)
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
    except Exception:
        data = request.POST
    return data


def validate_and_log_api_req(request):
    # Prefer "apikey" in REQUEST, but take either that or the
    # header value
    key = request.META.get("HTTP_X_API_KEY", None)
    key = request.REQUEST.get("apikey", key)

    if key is None:
        raise InvalidAPIKeyException(
            "key not found as 'apikey' param or 'X-API-Key' header")

    apikeys = APIKey.objects.filter(key=key)

    if len(apikeys) > 0:
        apikey = apikeys[0]
    else:
        raise InvalidAPIKeyException("key not found")

    if not apikey.enabled:
        raise InvalidAPIKeyException("key is not enabled")

    # Log the request
    reqstr = ",".join(["%s=%s" % (k, request.REQUEST[k])
                       for k in request.REQUEST])
    APILog(url=request.get_full_path(),
           remoteip=request.META["REMOTE_ADDR"],
           requestvars=reqstr,
           method=request.method,
           apikey=apikey,
           useragent=request.META.get("HTTP_USER_AGENT", ''),
           appver=request.META.get("HTTP_APPLICATIONVERSION", '')).save()

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
                response = HttpResponseBadRequest(str(bad_request))

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
    perms = {"plot": plot_or_tree_permissions(plot, user)}

    tree = plot.current_tree()
    if tree:
        perms["tree"] = plot_or_tree_permissions(tree, user)

    return perms


def plot_or_tree_permissions(obj, user):
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
    # Use the normal admin system
    else:
        can_delete = obj.user_can_delete(user)
        ###TODO
        ###OTM only support the concept of 'can edit' and 'can delete'
        ###but OTM2 defines 'delete' as 'can edit all fields'
        ###at least right now, so these are the same
        can_edit = can_delete

        ###TODO
        ###This ignores things like 'can delete if they created it'
        ###and such. Those business rules should, however, be
        ###put in 'user_can_delete'

    return {"can_delete": can_delete, "can_edit": can_edit}


def can_delete_tree_or_plot(obj, user):
    permissions = plot_or_tree_permissions(obj, user)
    if "can_delete" in permissions:
        return permissions["can_delete"]
    else:
        # This should never happen, but raising an exception ensures
        # that it will fail loudly if a future refactoring
        # introduces a bug.
        raise Exception("Expected the dict returned from "
                        "plot_or_tree_permissions to contain 'can_delete'")


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

    try:
        user = create_user(**data)
    except IntegrityError:
        response = HttpResponse()
        response.status_code = 409
        response.content = json.dumps(
            {'status': 'failure',
             'detail': 'Username %s exists' % data['username']})

        return response

    return {"status": "success", "id": user.pk}


@require_http_methods(["POST"])
@api_call()
@login_required
def add_tree_photo(request, plot_id):
    content_type = request.META.get('CONTENT_TYPE')
    if not content_type:
        # Older versions of the iOS client sent PNGs exclusively
        content_type = "image/png"

    file_type = content_type.lower().split('/')[-1]
    uploaded_image = ContentFile(request.body)
    uploaded_image.name = "plot_%s.%s" % (plot_id, file_type)

    treephoto = add_tree_photo(request.user.pk, plot_id, uploaded_image)

    return {"status": "success", "title": treephoto.title, "id": treephoto.pk}


@require_http_methods(["POST"])
@api_call()
@login_required
def add_profile_photo(request, user_id, title):
    uploaded_image = ContentFile(request.body)
    uploaded_image.name = "%s.png" % title

    add_user_photo(user_id, uploaded_image)

    return {"status": "success"}


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

    result_offset = int(request.REQUEST.get("offset", 0))
    num_results = min(int(request.REQUEST.get("length", 15)), 15)

    audits = Audit.objects.filter(instance=instance)\
                          .filter(user=user)\
                          .filter(model_in=['Tree', 'Plot'])\
                          .order_by('-created', 'id')

    audits = audits[result_offset:(result_offset+num_results)]

    keys = []
    for audit in audits:
        d = {}
        plot = extract_plot_from_audit(audit)
        d["plot_id"] = plot.pk

        if plot.pk:
            d["plot"] = plot_to_dict(
                plot, longform=True, user=user)

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

    return {"status": "success"}


@require_http_methods(["POST"])
@api_call()
def reset_password(request):
    resetform = PasswordResetForm({"email": request.REQUEST["email"]})

    if (resetform.is_valid()):
        opts = {
            'use_https': request.is_secure(),
            'token_generator': default_token_generator,
            'from_email': None,
            'email_template_name': 'reset_email_password.html',
            'request': request}

        resetform.save(**opts)
        return {"status": "success"}
    else:
        raise HttpBadRequestException()


@require_http_methods(["GET"])
@api_call()
def version(request):
    """ API Request

    Get version information for OTM and the API. Generally, the API
    is unstable for any API version < 1 and minor changes
    (i.e. 1.4,1.5,1.6) represent no break in existing functionality

    Verb: GET
    Params: None
    Output:
      {
        otm_version, string -> Open Tree Map Version (i.e. 1.0.2)
        api_version, string -> API version (i.e. 1.6)
      }

    """
    return {"otm_version": settings.OTM_VERSION,
            "api_version": settings.API_VERSION}


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
        resized = img.resize((144, 132), Image.ANTIALIAS)
        response = HttpResponse(mimetype="image/png")
        resized.save(response, "PNG")
        return response
    else:
        raise HttpBadRequestException('invalid url (missing objects)')


@require_http_methods(["GET"])
@instance_request
@api_call()
def get_plot_list(request, instance):
    """ API Request

    Get a list of all plots in the database. This is meant to be a
    lightweight listing service. To get more details about a plot
    use the ^plot/{id}$ service

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
    start = int(request.REQUEST.get("offset", "0"))
    size = min(int(request.REQUEST.get("size", "100")), 10000)
    end = size + start

    # order_by prevents testing weirdness
    plots = Plot.objects.filter(instance=instance)\
                        .order_by('id')[start:end]

    return plots_to_list_of_dict(plots, user=request.user)


@require_http_methods(["GET"])
@api_call()
def species_list(request, lat=None, lon=None):
    allspecies = Species.objects.all()

    return [species_to_dict(z) for z in allspecies]


@require_http_methods(["GET"])
@api_call()
@login_optional
def plots_closest_to_point(request, lat=None, lon=None):
    ###TODO: Need to pin to an instance
    instance = Instance.objects.all()[0]
    point = Point(float(lon), float(lat), srid=4326)

    try:
        max_plots = int(request.GET.get('max_plots', '1'))
    except ValueError:
        raise HttpBadRequestException(
            'The max_plots parameter must be a number between 1 and 500')

    if max_plots > 500 or max_plots < 1:
        raise HttpBadRequestException(
            'The max_plots parameter must be a number between 1 and 500')

    try:
        distance = float(request.GET.get(
            'distance', settings.MAP_CLICK_RADIUS))

    except ValueError:
        raise HttpBadRequestException(
            'The distance parameter must be a number')

    # 100 meters
    plots = Plot.objects.distance(point)\
                        .filter(instance=instance)\
                        .filter(geom__distance_lte=(point, D(m=distance)))\
                        .order_by('distance')[0:max_plots]

    if 'q' in request.REQUEST:
        q = request.REQUEST['q']
        plots = plots.filter(create_filter(q))

    return plots_to_list_of_dict(
        plots, longform=True, user=request.user)


def str2bool(ahash, akey):
    if akey in ahash:
        return ahash[akey] == "true"
    else:
        return None


def plots_to_list_of_dict(plots, longform=False, user=None):
    return [plot_to_dict(plot, longform=longform, user=user)
            for plot in plots]


def point_wkt_to_dict(wkt):
    point = fromstr(wkt)
    return {
        'y': point.y,
        'x': point.x,
        'srid': '3857'
    }


def pending_edit_to_dict(pending_edit):
    if pending_edit.field == 'geometry':
        # Pending geometry edits are stored as WKT
        pending_value = point_wkt_to_dict(pending_edit.current_value)
    else:
        pending_value = pending_edit.current_value

    return {
        'id': pending_edit.pk,
        'submitted': datetime_to_iso_string(pending_edit.created),
        'value': pending_value,
        'username': pending_edit.user.username
    }


def plot_to_dict(plot, longform=False, user=None):
    pending_edit_dict = {}
    current_tree = plot.current_tree()
    if current_tree:
        tree_dict = {"id": current_tree.pk}

        if current_tree.species:
            tree_dict["species"] = current_tree.species.pk
            tree_dict["species_name"] = current_tree.species.common_name
            tree_dict["sci_name"] = current_tree.species.scientific_name

        if current_tree.diameter:
            tree_dict["dbh"] = current_tree.diameter

        if current_tree.height:
            tree_dict["height"] = current_tree.height

        if current_tree.canopy_height:
            tree_dict["canopy_height"] = current_tree.canopy_height

        #TODO: Support for tree images
        # images = current_tree.treephoto_set.all()

        # if len(images) > 0:
        #     tree_dict["images"] = [{"id": image.pk,
        # "title": image.title, "url": image.photo.url}
        #                            for image in images]

        pending_edit_dict = {}

        if longform:
            tree_dict['eco'] = tree_resource_to_dict(current_tree)
            tree_dict['readonly'] = current_tree.readonly

            tree_field_reverse_property_name_dict = {'species_id': 'species'}
            for audit in current_tree.get_active_pending_audits():
                raw_field_name = audit.field

                if raw_field_name in tree_field_reverse_property_name_dict:
                    field_name = tree_field_reverse_property_name_dict.get(
                        raw_field_name)
                else:
                    field_name = raw_field_name

                if 'tree.' + field_name not in pending_edit_dict:
                    pending_edit_dict['tree.' + field_name] = {
                        'latest_value': audit.previous_value,
                        'pending_edits': []}

                pend_dict = pending_edit_to_dict(audit)
                if field_name == 'species':
                    species_set = Species.objects.filter(
                        pk=audit.current_value)
                    if species_set:
                        pend_dict['related_fields'] = {
                            'tree.sci_name': species_set[0].scientific_name,
                            'tree.species_name': species_set[0].common_name
                        }
                pending_edit_dict['tree.' + field_name]['pending_edits']\
                    .append(pend_dict)

    else:
        tree_dict = None

    base = {
        "id": plot.pk,
        "plot_width": plot.width,
        "plot_length": plot.length,
        "readonly": plot.readonly,
        "tree": tree_dict,
        "geom": {
            "srid": plot.geom.srid,
            "y": plot.geom.y,
            "x": plot.geom.x
        }
    }

    if user:
        base["perm"] = plot_permissions(plot, user)

    if longform:

        plot_field_reverse_property_name_dict = {
            'width': 'plot_width',
            'length': 'plot_length'
        }

        for audit in plot.get_active_pending_audits():
            raw_field_name = audit.field
            if raw_field_name in plot_field_reverse_property_name_dict:
                field_name = plot_field_reverse_property_name_dict.get(
                    raw_field_name)
            else:
                field_name = raw_field_name

            if field_name == 'geom':
                latest_value = point_wkt_to_dict(audit.previous_value)
            else:
                latest_value = audit.current_value

            if field_name not in pending_edit_dict:
                pending_edit_dict[field_name] = {
                    'latest_value': latest_value,
                    'pending_edits': []}

            pending_edit_dict[field_name]['pending_edits'].append(
                pending_edit_to_dict(audit))

        base['pending_edits'] = pending_edit_dict

    return base


def tree_resource_to_dict(tree):
    if tree.species and tree.species.itree_code and tree.diameter:
        return tree_benefits(tree.instance, tree.pk)
    else:
        return {}


def species_to_dict(s):
    return {
        "id": s.pk,
        "scientific_name": s.scientific_name,
        "genus": s.genus,
        "species": s.species,
        "cultivar": s.cultivar_name,
        "common_name": s.common_name}


def user_to_dict(user):
    #TODO: permissions?
    # what are these in OTM2 vs OTM1
    # user_type permissions need to be updated
    # is this even used in the app?
    return {
        "id": user.pk,
        "reputation": user.reputation,
        "username": user.username
        #"permissions": list(user.get_all_permissions()),
        #"user_type": user_access_type(user)
        }


#TODO: All of this logic should probably be
# moved to the geocoder app
# not sure what we should do about BBOX settings
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

    if (('OMGEO_GEOCODER_SOURCES' in dir(settings)
         and settings.OMGEO_GEOCODER_SOURCES is not None)):
        geocoder = Geocoder(settings.OMGEO_GEOCODER_SOURCES)
    else:
        geocoder = Geocoder()

    results = geocoder.geocode(query)
    if results is not False:
        response = []
        for result in results:
            # some geocoders do not support passing a bounding box filter
            if result_in_bounding_box(result):
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
        # This is not a very helpful error message, but omgeo as of
        # v1.2 does not report failure details.
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
    The new plot/tree form requires specific field names that do not
    directly match up with the model objects (e.g. the form expects
    a 'species_id' field) so this helper function renames keys in
    the dictionary to match what the form expects
    '''
    field_map = {'species': 'species_id',
                 'width': 'plot_width',
                 'length': 'plot_length'}
    for map_key in field_map.keys():
        if map_key in request_dict:
            request_dict[field_map[map_key]] = request_dict[map_key]
            del request_dict[map_key]
    return request_dict


@require_http_methods(["POST"])
@instance_request
@api_call()
@login_required
def create_plot_optional_tree(request, instance):
    response = HttpResponse()

    # Unit tests fail to access request.body
    request_dict = json_from_request(request)

    # The Django form used to validate and save plot and tree
    # information expects a flat dictionary. Allowing the tree
    # and geometry details to be in nested dictionaries in API
    # calls clarifies, to API clients, the distinction between
    # Plot and Tree and groups the coordinates along with their
    # spatial reference
    flatten_plot_dict_with_tree_and_geometry(request_dict)

    # The new plot/tree form requires specific field names that
    # do not directly match up with the model objects (e.g. the
    # form expects a 'species_id' field) so this helper function
    # renames keys in the dictionary to match what the form expects
    rename_plot_request_dict_fields(request_dict)

    plot = create_plot(request.user, instance, **request_dict)

    if type(plot) is list:
        response.status_code = 400
        response.content = json.dumps({'error': plot})
    else:
        response.status_code = 201
        new_plot = plot_to_dict(plot, longform=True, user=request.user)
        response.content = json.dumps(new_plot)

    return response


@require_http_methods(["GET"])
@api_call()
@login_optional
def get_plot(request, plot_id):
    return plot_to_dict(Plot.objects.get(pk=plot_id),
                        longform=True, user=request.user)


def compare_fields(v1, v2):
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
        if (('version-threshold' in conversion
             and app_version['platform'] in conversion['version-threshold'])):
            threshold_string = conversion.get('version-threshold')\
                                         .get(app_version['platform'])

            # If the threshold is not parsable as a version number,
            # we want this method to crash hard.
            # The CHOICE_CONVERSIONS are misconfigured.
            threshold = StrictVersion(threshold_string)

            try:
                version = StrictVersion(app_version['version'])
            except ValueError:
                # If the version number reported from the app is
                # not parsable as a version number then we assume
                # the app is an old version and that we do
                # need to convert the values.
                return True

            return version < threshold
        else:
            # If a version threshold is not defined for the platform
            # specified in the ApplicationVersion header or the
            # ApplicationVersion header is missing or does not match
            # anything
            return True
    else:
        # If the settings.CHOICE_CONVERSIONS hash does not contain
        # the attribute name then no conversion is required
        return False


@require_http_methods(["PUT"])
@api_call()
@instance_request
@login_required
def update_plot_and_tree(request, instance, plot_id):

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
        response.content = json.dumps({
            "error": "No plot with id %s" % plot_id})
        return response

    request_dict = json_from_request(request)

    flatten_plot_dict_with_tree_and_geometry(request_dict)

    plot_field_whitelist = ['plot_width', 'plot_length', 'type',
                            'geocoded_address', 'edit_address_street',
                            'address_city', 'address_street', 'address_zip',
                            'power_lines', 'sidewalk_damage']

    # The Django form that creates new plots expects a 'plot_width'
    # parameter but the Plot model has a 'width' parameter so this
    # dict acts as a translator between request keys and model field names
    plot_field_property_name_dict = {
        'plot_width': 'width',
        'plot_length': 'length',
        'power_lines': 'powerline_conflict_potential'}

    plot_was_edited = False
    for plot_field_name in request_dict.keys():
        if plot_field_name in plot_field_whitelist:
            if plot_field_name in plot_field_property_name_dict:
                new_name = plot_field_property_name_dict[plot_field_name]
            else:
                new_name = plot_field_name
            new_value = request_dict[plot_field_name]
            if not compare_fields(get_attr_with_choice_correction(
                    request, plot, new_name), new_value):
                set_attr_with_choice_correction(
                    request, plot, new_name, new_value)
                plot_was_edited = True

    # TODO: Standardize on lon or lng
    if 'lat' in request_dict or 'lon' in request_dict or 'lng' in request_dict:
        new_geometry = Point(x=plot.geom.x, y=plot.geom.y)
        if 'lat' in request_dict:
            new_geometry.y = request_dict['lat']
        if 'lng' in request_dict:
            new_geometry.x = request_dict['lng']
        if 'lon' in request_dict:
            new_geometry.x = request_dict['lon']

        if plot.geom.x != new_geometry.x or plot.geom.y != new_geometry.y:
            plot.geom = new_geometry
            plot_was_edited = True

    if plot_was_edited:
        plot.save_with_user(request.user)

    tree_was_edited = False
    tree_was_added = False
    tree = plot.current_tree()
    tree_field_whitelist = ['species', 'diameter', 'height', 'canopy_height',
                            'canopy_condition', 'condition', 'pests']

    for tree_field in Tree._meta.fields:
        if ((tree_field.name in request_dict and
             tree_field.name in tree_field_whitelist)):
            if tree is None:
                tree = Tree(plot=plot, instance=instance,
                            created_by=request.user)

                tree.plot = plot
                tree.last_updated_by = request.user
                tree.save_with_user(request.user)
                tree_was_added = True
            if tree_field.name == 'species':
                try:
                    if (((tree.species and
                          tree.species.pk != request_dict[tree_field.name])
                         or
                         (not tree.species
                          and request_dict[tree_field.name]))):
                        tree.species = Species.objects.get(
                            pk=request_dict[tree_field.name])
                        tree_was_edited = True
                except Exception:
                    response.status_code = 400
                    response.content = json.dumps(
                        {"error": "No species with id %s" %
                         request_dict[tree_field.name]})
                    return response
            else:  # tree_field.name != 'species'
                if not compare_fields(
                        get_attr_with_choice_correction(
                            request, tree, tree_field.name),
                        request_dict[tree_field.name]):
                    set_attr_with_choice_correction(
                        request, tree, tree_field.name,
                        request_dict[tree_field.name])

                    tree_was_edited = True

    if tree_was_added or tree_was_edited:
        tree.save_with_user(request.user)

    full_plot = Plot.objects.get(pk=plot.id)
    return_dict = plot_to_dict(full_plot, longform=True, user=request.user)
    response.status_code = 200
    response.content = json.dumps(return_dict)
    return response


def _approve_or_reject_pending_edit(
        request, instance, user, pending_edit_id, approve):
    audit = Audit.objects.get(pk=pending_edit_id, instance=instance)
    approve_or_reject_audit_and_apply(audit, user, approve)

    updated_plot = extract_plot_from_audit(audit)

    # Reject remaining audits on specified field if
    # we approved this audit
    # TODO: Should this logic be moved to app_or_rej_audit_and_ap?
    if approve:
        for pending_audit in updated_plot.get_active_pending_audits()\
                                         .filter(field=audit.field):
            approve_or_reject_audit_and_apply(pending_audit, user, False)

    return plot_to_dict(updated_plot, longform=True)


@require_http_methods(["POST"])
@instance_request
@api_call()
@login_required
def approve_pending_edit(request, instance, pending_edit_id):
    return _approve_or_reject_pending_edit(
        request, instance, request.user, pending_edit_id, True)


@require_http_methods(["POST"])
@instance_request
@api_call()
@login_required
def reject_pending_edit(request, instance, pending_edit_id):
    return _approve_or_reject_pending_edit(
        request, instance, request.user, pending_edit_id, False)


@require_http_methods(["DELETE"])
@api_call()
@instance_request
@login_required
@transaction.commit_on_success
def remove_plot(request, instance, plot_id):
    plot = get_object_or_404(Plot, pk=plot_id, instance=instance)
    try:
        plot.delete_with_user(request.user)
        return {"ok": True}
    except Exception:
        raise PermissionDenied(
            '%s does not have permission to delete plot %s' %
            (request.user.username, plot_id))


@require_http_methods(["DELETE"])
@api_call()
@instance_request
@login_required
@transaction.commit_on_success
def remove_current_tree_from_plot(request, instance, plot_id):
    plot = get_object_or_404(Plot, pk=plot_id, instance=instance)
    tree = plot.current_tree()

    if tree:
        try:
            tree.delete_with_user(request.user)
            updated_plot = Plot.objects.get(pk=plot_id)
            return plot_to_dict(
                updated_plot, longform=True, user=request.user)
        except:
            raise PermissionDenied(
                '%s does not have permission to the '
                'current tree from plot %s' %
                (request.user.username, plot_id))
    else:
        raise HttpResponseBadRequest(
            "Plot %s does not have a current tree" % plot_id)


@require_http_methods(["GET"])
@instance_request
@api_call()
def get_current_tree_from_plot(request, instance, plot_id):
    plot = get_object_or_404(Plot, pk=plot_id, instance=instance)
    if plot.current_tree():
        plot_dict = plot_to_dict(plot, longform=True)

        return plot_dict['tree']
    else:
        raise HttpResponseBadRequest(
            "Plot %s does not have a current tree" % plot_id)

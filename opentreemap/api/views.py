# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
from PIL import Image
from functools import wraps

from omgeo import Geocoder
from omgeo.places import PlaceQuery, Viewbox

from django.core.exceptions import PermissionDenied, ValidationError
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.http import (HttpResponse, HttpResponseBadRequest,
                         HttpResponseForbidden)
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator

from opentreemap.util import route

from treemap.models import Plot, Tree
from treemap.views import (create_user, get_tree_photos, species_list,
                           upload_user_photo, context_dict_for_plot)

from treemap.decorators import instance_request, json_api_call
from treemap.exceptions import HttpBadRequestException
from treemap.audit import Audit, approve_or_reject_audit_and_apply

from api.models import APIKey, APILog
from api.auth import login_required, create_401unauthorized, login_optional

from instance import instance_info
from plots import plots_closest_to_point, get_plot, update_or_create_plot
from user import user_info


class HttpConflictException(Exception):
    pass


class InvalidAPIKeyException(Exception):
    pass


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


@require_http_methods(["GET"])
@api_call()
def status(request):
    return [{'api_version': 'v2',
             'status': 'online',
             'message': ''}]


@require_http_methods(["POST"])
@api_call()
@transaction.commit_on_success
def register(request):
    data = json.loads(request.body)

    try:
        user = create_user(**data)
    except ValidationError as e:
        response = HttpResponse()
        response.status_code = 400
        response.content = json.dumps({'status': 'failure',
                                       'detail': e.message_dict})

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

    plot = get_object_or_404(Plot, pk=plot_id)
    tree = plot.current_tree()

    if tree:
        tree_pk = tree.pk
    else:
        tree_pk = None

    treephoto, _ = add_tree_photo(
        request, plot.instance, plot.pk, tree_pk)

    return {"status": "success", "title": '', "id": treephoto['id']}


@require_http_methods(["POST"])
@api_call()
@login_required
def add_profile_photo(request, user_id, _):
    """
    Uploads a user profile photo.
    The third parameter to this function exists for backwards compatibility
    reasons, but is ignored and unused.
    """
    user = get_object_or_404(User, id=user_id)
    if user != request.user:
        return HttpResponseForbidden()

    return upload_user_photo(request, user_id)


def extract_plot_from_audit(audit):
    if audit.model == 'Plot':
        return Plot.objects.get(pk=audit.model_id)
    elif audit.model == 'Tree':
        return Tree.objects.get(id=audit.model_id).plot


@require_http_methods(["GET"])
@api_call()
@instance_request
@login_required
def edits(request, instance, user_id):
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
            d["plot"] = context_dict_for_plot(plot, user=user)

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
        otm_version, string -> OpenTreeMap Version (i.e. 1.0.2)
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

    return [context_dict_for_plot(plot, user=request.user) for plot in plots]


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

    return context_dict_for_plot(updated_plot, user=request.user)


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
            return context_dict_for_plot(
                updated_plot, user=request.user)
        except:
            raise PermissionDenied(
                '%s does not have permission to the '
                'current tree from plot %s' %
                (request.user.username, plot_id))
    else:
        raise HttpResponseBadRequest(
            "Plot %s does not have a current tree" % plot_id)


plots_closest_to_point_endpoint = login_optional(
    instance_request(
        csrf_exempt(json_api_call(
            plots_closest_to_point))))

instance_info_endpoint = login_optional(
    instance_request(
        csrf_exempt(json_api_call(
            instance_info))))

login_endpoint = csrf_exempt(
    json_api_call(login_required(user_info)))

plots_endpoint = json_api_call(
    route(
        POST=login_required(
            instance_request(
                update_or_create_plot)),
        GET=login_optional(
            instance_request(
                get_plot_list))))

plot_endpoint = json_api_call(
    route(
        GET=login_optional(
            instance_request(get_plot)),
        PUT=login_required(
            instance_request(update_or_create_plot)),
        DELETE=login_required(
            instance_request(remove_plot))))

species_list_endpoint = instance_request(
    json_api_call(
        route(GET=species_list)))

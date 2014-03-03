# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json

from omgeo import Geocoder
from omgeo.places import PlaceQuery, Viewbox

from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator

from opentreemap.util import route

from treemap.models import Plot, Tree
from treemap.views import (species_list, upload_user_photo,
                           context_dict_for_plot, add_tree_photo)

from treemap.decorators import json_api_call, return_400_if_validation_errors
from treemap.decorators import api_instance_request as instance_request
from treemap.exceptions import HttpBadRequestException
from treemap.audit import Audit, approve_or_reject_audit_and_apply

from api.auth import (create_401unauthorized, check_signature,
                      check_signature_and_require_login, login_required)

from api.instance import instance_info, instances_closest_to_point
from api.plots import plots_closest_to_point, get_plot, update_or_create_plot
from api.user import user_info, create_user


class HttpConflictException(Exception):
    pass


def datetime_to_iso_string(d):
    if d:
        return d.strftime('%Y-%m-%d %H:%M:%S')
    else:
        return None


def status(request):
    return [{'api_version': 'v2',
             'status': 'online',
             'message': ''}]


@require_http_methods(["POST"])
@json_api_call
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
@json_api_call
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
            d["plot"] = context_dict_for_plot(
                request.instance,
                plot,
                user=user,
                supports_eco=request.instance_supports_ecobenefits)

        d["id"] = audit.pk
        d["name"] = audit.display_action
        d["created"] = datetime_to_iso_string(audit.created)
        d["value"] = audit.current_value

        keys.append(d)

    return keys


@require_http_methods(["PUT"])
@json_api_call
@login_required
def update_password(request, user_id):
    data = json.loads(request.body)

    pw = data["password"]

    user = User.objects.get(pk=user_id)

    user.set_password(pw)
    user.save()

    return {"status": "success"}


@require_http_methods(["POST"])
@json_api_call
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
@instance_request
@json_api_call
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

    def ctxt_for_plot(plot):
        return context_dict_for_plot(
            request.instance,
            plot,
            user=request.user,
            supports_eco=request.instance_supports_ecobenefits)

    return [ctxt_for_plot(plot) for plot in plots]


#TODO: All of this logic should probably be
# moved to the geocoder app
# not sure what we should do about BBOX settings
@require_http_methods(["GET"])
@json_api_call
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

    return context_dict_for_plot(
        request.instance,
        updated_plot,
        user=request.user,
        supports_eco=request.instance_supports_ecobenefits)


@require_http_methods(["POST"])
@instance_request
@json_api_call
@login_required
def approve_pending_edit(request, instance, pending_edit_id):
    return _approve_or_reject_pending_edit(
        request, instance, request.user, pending_edit_id, True)


@require_http_methods(["POST"])
@instance_request
@json_api_call
@login_required
def reject_pending_edit(request, instance, pending_edit_id):
    return _approve_or_reject_pending_edit(
        request, instance, request.user, pending_edit_id, False)


@require_http_methods(["DELETE"])
@json_api_call
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
@json_api_call
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
                request.instance,
                updated_plot,
                user=request.user,
                supports_eco=request.instance_supports_ecobenefits)
        except:
            raise PermissionDenied(
                '%s does not have permission to the '
                'current tree from plot %s' %
                (request.user.username, plot_id))
    else:
        raise HttpResponseBadRequest(
            "Plot %s does not have a current tree" % plot_id)


def add_photo(request, instance, plot_id):
    treephoto, _ = add_tree_photo(request, instance, plot_id)

    return treephoto


# Note that API requests going to private instances require
# authentication "login_optional" before they can access they
# instance data

plots_closest_to_point_endpoint = check_signature(
    instance_request(
        json_api_call(
            plots_closest_to_point)))

instances_closest_to_point_endpoint = check_signature(
    instance_request(
        json_api_call(
            instances_closest_to_point)))

instance_info_endpoint = check_signature(
    instance_request(
        json_api_call(
            instance_info)))

plots_endpoint = check_signature(
    instance_request(
        json_api_call(
            route(
                POST=login_required(
                    update_or_create_plot),
                GET=get_plot_list))))

plot_endpoint = check_signature(
    instance_request(
        json_api_call(
            route(
                GET=get_plot,
                PUT=login_required(update_or_create_plot),
                DELETE=login_required(remove_plot)))))

species_list_endpoint = check_signature(
    json_api_call(
        route(GET=species_list)))

user_endpoint = check_signature(
    json_api_call(
        route(
            GET=login_required(
                user_info),
            POST=return_400_if_validation_errors(
                create_user))))

add_photo_endpoint = check_signature_and_require_login(
    json_api_call(
        route(
            POST=instance_request(
                return_400_if_validation_errors(add_photo)))))

status_view = check_signature(
    json_api_call(
        route(
            GET=status)))

version_view = check_signature(
    json_api_call(
        route(
            GET=version)))

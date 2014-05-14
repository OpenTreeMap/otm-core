# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from opentreemap.util import route
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import etag

from treemap.decorators import (json_api_call, render_template, login_or_401,
                                require_http_method, string_as_file_call,
                                requires_feature,
                                creates_instance_user, instance_request,
                                username_matches_request_user,
                                admin_instance_request)

from treemap.views.views import *  # NOQA
from treemap.views.views import (_get_map_view_context, _map_feature_hash,  # NOQA
                                 _search_hash, _user_instances, _color_re)  # NOQA

tree_detail_view = instance_request(tree_detail)

edits_view = instance_request(
    requires_feature('recent_edits_report')(
        render_template('treemap/edits.html', edits)))

index_view = instance_request(index)

map_view = instance_request(
    render_template('treemap/map.html', _get_map_view_context))

get_map_feature_detail_view = instance_request(render_map_feature_detail)

get_map_feature_add_view = instance_request(render_map_feature_add)

edit_plot_detail_view = login_required(
    instance_request(
        creates_instance_user(
            render_template('treemap/plot_detail.html', plot_detail))))

update_map_feature_detail_view = login_or_401(
    json_api_call(
        instance_request(
            creates_instance_user(update_map_feature_detail))))

delete_tree_view = login_or_401(
    json_api_call(
        instance_request(
            creates_instance_user(delete_tree))))

delete_map_feature_view = login_or_401(
    json_api_call(
        instance_request(
            creates_instance_user(delete_map_feature))))

get_plot_eco_view = instance_request(etag(_map_feature_hash)(
    render_template('treemap/partials/plot_eco.html', plot_detail)))

get_map_feature_sidebar_view = instance_request(etag(_map_feature_hash)(
    render_template('treemap/partials/sidebar.html', plot_detail)))

map_feature_popup_view = instance_request(etag(_map_feature_hash)(
    render_template('treemap/partials/map_feature_popup.html',
                    map_feature_popup)))

plot_accordion_view = instance_request(
    render_template('treemap/plot_accordion.html', plot_detail))

add_map_feature_view = require_http_method("POST")(
    login_or_401(
        json_api_call(
            instance_request(
                creates_instance_user(add_map_feature)))))

root_settings_js_view = render_template('treemap/settings.js',
                                        {'BING_API_KEY':
                                         settings.BING_API_KEY},
                                        mimetype='application/javascript')

instance_settings_js_view = instance_request(
    render_template('treemap/settings.js',
                    {'BING_API_KEY': settings.BING_API_KEY},
                    mimetype='application/javascript'))

boundary_to_geojson_view = json_api_call(instance_request(boundary_to_geojson))
boundary_autocomplete_view = instance_request(
    json_api_call(boundary_autocomplete))

search_tree_benefits_view = instance_request(
    etag(_search_hash)(
        render_template('treemap/partials/eco_benefits.html',
                        search_tree_benefits)))

species_list_view = json_api_call(instance_request(species_list))

user_view = render_template("treemap/user.html", user)

update_user_view = require_http_method("PUT")(
    username_matches_request_user(
        json_api_call(update_user)))

user_audits_view = render_template("treemap/recent_user_edits.html",
                                   user_audits)

upload_user_photo_view = require_http_method("POST")(
    username_matches_request_user(
        json_api_call(upload_user_photo)))

instance_not_available_view = render_template(
    "treemap/instance_not_available.html")

unsupported_view = render_template("treemap/unsupported.html")

landing_view = render_template("base.html")

add_tree_photo_endpoint = require_http_method("POST")(
    login_or_401(
        instance_request(
            creates_instance_user(
                render_template("treemap/partials/tree_carousel.html",
                                add_tree_photo_view)))))

# FIXME: the returned template is now probably misnamed
add_map_feature_photo_endpoint = require_http_method("POST")(
    login_or_401(
        instance_request(
            creates_instance_user(
                render_template("treemap/partials/tree_carousel.html",
                                add_map_feature_photo_view)))))

scss_view = require_http_method("GET")(
    string_as_file_call("text/css", compile_scss))

photo_review_endpoint = admin_instance_request(
    route(
        GET=render_template("treemap/photo_review.html",
                            photo_review)))

photo_review_partial_endpoint = admin_instance_request(
    route(
        GET=render_template("treemap/partials/photo_review.html",
                            photo_review)))

next_photo_endpoint = admin_instance_request(
    route(
        GET=render_template("treemap/partials/photo.html",
                            next_photo)))

approve_or_reject_photo_view = admin_instance_request(
    route(POST=approve_or_reject_photo))

static_page_view = instance_request(
    render_template("treemap/staticpage.html", static_page))

forgot_username_view = route(
    GET=render_template('treemap/forgot_username.html'),
    POST=render_template('treemap/forgot_username_done.html', forgot_username))

error_404_view = render_template('404.html', statuscode=404)
error_500_view = render_template('500.html', statuscode=500)
error_503_view = render_template('503.html', statuscode=503)

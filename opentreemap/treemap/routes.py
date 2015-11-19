# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from functools import partial

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import etag

from django_tinsel.utils import decorate as do
from django_tinsel.decorators import (route, json_api_call, render_template,
                                      string_to_response,
                                      username_matches_request_user)

from treemap.decorators import (login_or_401, return_400_if_validation_errors,
                                require_http_method, requires_feature,
                                creates_instance_user, instance_request,
                                admin_instance_request, json_api_edit)

import treemap.views.user as user_views
import treemap.views.photo as photo_views
import treemap.views.tree as tree_views
import treemap.views.misc as misc_views
import treemap.views.map_feature as feature_views


add_map_feature_photo_do = partial(
    do,
    require_http_method("POST"),
    login_or_401,
    instance_request,
    creates_instance_user,
    render_template('treemap/partials/photo_carousel.html'))

#####################################
# misc content views
#####################################

edits_page = do(
    instance_request,
    requires_feature('recent_edits_report'),
    render_template('treemap/edits.html'),
    misc_views.edits)

index_page = instance_request(misc_views.index)

map_page = do(
    instance_request,
    render_template('treemap/map.html'),
    misc_views.get_map_view_context)

static_page = do(
    instance_request,
    render_template('treemap/staticpage.html'),
    misc_views.static_page)

instance_not_available = render_template(
    'treemap/instance_not_available.html')()

landing_page = render_template('base.html')()

unsupported_page = render_template('treemap/unsupported.html')()

instances_geojson = do(
    json_api_call,
    misc_views.public_instances_geojson)

error_404_page = misc_views.error_page(status_code=404)
error_500_page = misc_views.error_page(status_code=500)
error_503_page = misc_views.error_page(status_code=503)

#####################################
# utility views
#####################################

root_settings_js = render_template('treemap/settings.js')(
    {'BING_API_KEY':
     settings.BING_API_KEY},
    content_type='application/javascript')

instance_settings_js = instance_request(root_settings_js)

boundary_to_geojson = do(
    json_api_call,
    instance_request,
    misc_views.boundary_to_geojson)

boundary_autocomplete = do(
    json_api_call,
    instance_request,
    misc_views.boundary_autocomplete)

species_list = do(
    json_api_call,
    instance_request,
    misc_views.species_list)

compile_scss = do(
    require_http_method("GET"),
    string_to_response("text/css"),
    misc_views.compile_scss)

#####################################
# mapfeature
#####################################

add_map_feature = do(
    instance_request,
    route(
        GET=feature_views.render_map_feature_add,
        POST=do(
            json_api_edit,
            return_400_if_validation_errors,
            feature_views.add_map_feature)))

map_feature_detail = do(
    instance_request,
    route(
        GET=feature_views.render_map_feature_detail,
        ELSE=do(
            json_api_edit,
            return_400_if_validation_errors,
            route(
                PUT=feature_views.update_map_feature_detail,
                DELETE=feature_views.delete_map_feature))))

map_feature_accordion = do(
    instance_request,
    render_template('treemap/partials/map_feature_accordion.html'),
    feature_views.context_map_feature_detail)

get_map_feature_sidebar = do(
    instance_request,
    etag(feature_views.map_feature_hash),
    render_template('treemap/partials/sidebar.html'),
    feature_views.context_map_feature_detail)

map_feature_popup = do(
    instance_request,
    etag(feature_views.map_feature_hash),
    render_template('treemap/partials/map_feature_popup.html'),
    feature_views.map_feature_popup)

add_map_feature_photo = add_map_feature_photo_do(
    feature_views.add_map_feature_photo)

rotate_map_feature_photo = add_map_feature_photo_do(
    feature_views.rotate_map_feature_photo)

map_feature_photo_detail = do(
    instance_request,
    require_http_method('GET'),
    render_template('treemap/map_feature_photo_detail.html'),
    feature_views.map_feature_photo_detail)

favorite_map_feature = do(
    instance_request,
    require_http_method('POST'),
    json_api_edit,
    feature_views.favorite_map_feature)

unfavorite_map_feature = do(
    instance_request,
    require_http_method('POST'),
    json_api_edit,
    feature_views.unfavorite_map_feature)

edit_map_feature_detail = do(
    login_required,
    instance_request,
    creates_instance_user,
    feature_views.render_map_feature_detail)


#####################################
# plot
#####################################

get_plot_eco = do(
    instance_request,
    etag(feature_views.map_feature_hash),
    render_template('treemap/partials/plot_eco.html'),
    feature_views.plot_detail)


#####################################
# tree
#####################################

delete_tree = do(
    instance_request,
    json_api_edit,
    route(DELETE=tree_views.delete_tree))

tree_detail = instance_request(tree_views.tree_detail)

search_tree_benefits = do(
    instance_request,
    etag(tree_views.search_hash),
    render_template('treemap/partials/eco_benefits.html'),
    tree_views.search_tree_benefits)

add_tree_photo = add_map_feature_photo_do(tree_views.add_tree_photo)

#####################################
# user
#####################################

instance_user_page = user_views.instance_user

instance_user_audits = user_views.instance_user_audits

profile_to_user_page = user_views.profile_to_user

user = route(
    GET=render_template('treemap/user.html')(user_views.user),
    PUT=do(
        require_http_method("PUT"),
        username_matches_request_user,
        json_api_call,
        return_400_if_validation_errors,
        user_views.update_user))

user_audits = do(
    render_template('treemap/recent_user_edits.html'),
    user_views.user_audits)

upload_user_photo = do(
    require_http_method("POST"),
    username_matches_request_user,
    json_api_call,
    return_400_if_validation_errors,
    user_views.upload_user_photo)

forgot_username = route(
    GET=render_template('treemap/forgot_username.html')(),
    POST=do(
        render_template('treemap/forgot_username_done.html'),
        return_400_if_validation_errors,
        user_views.forgot_username))

#####################################
# photo
#####################################

photo_review = do(
    require_http_method("GET"),
    admin_instance_request,
    render_template('treemap/photo_review.html'),
    photo_views.photo_review)

photo_review_partial = do(
    require_http_method("GET"),
    admin_instance_request,
    render_template('treemap/partials/photo_review.html'),
    photo_views.photo_review)

approve_or_reject_photos = do(
    require_http_method("POST"),
    admin_instance_request,
    render_template('treemap/partials/photo_review.html'),
    photo_views.approve_or_reject_photos)

# -*- coding: utf-8 -*-
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from functools import partial

from django_tinsel.decorators import route, render_template, json_api_call
from django_tinsel.utils import decorate as do

import manage_treemap.views.management as views
import manage_treemap.views.fields as field_views
import manage_treemap.views.photo as photo_views
import manage_treemap.views.green_infrastructure as green_infrastructure_views

from importer.views import list_imports
from manage_treemap.views import update_instance_fields_with_validator
from manage_treemap.views.udf import udf_bulk_update, udf_create, udf_list, \
    udf_delete_popup, udf_delete, udf_update_choice
from otm_comments.views import comment_moderation
from treemap.decorators import (require_http_method, admin_instance_request,
                                return_400_if_validation_errors)

admin_route = lambda **kwargs: admin_instance_request(route(**kwargs))

json_do = partial(do, json_api_call, return_400_if_validation_errors)

management = do(
    require_http_method('GET'),
    views.management_root)

admin_counts = admin_route(
    GET=do(json_api_call, views.admin_counts)
)

site_config = admin_route(
    GET=do(render_template('manage_treemap/basic.html'),
           views.site_config_basic_info),
    PUT=json_do(update_instance_fields_with_validator,
                views.site_config_validator)
)

external_link = admin_route(
    GET=do(render_template('manage_treemap/link.html'),
           views.external_link),
    PUT=json_do(views.update_external_link)
)

branding = admin_route(
    GET=do(render_template('manage_treemap/branding.html'),
           views.branding),
    PUT=json_do(update_instance_fields_with_validator,
                views.branding_validator)
)

embed = admin_route(
    GET=do(render_template('manage_treemap/embed.html'),
           views.embed)
)

update_logo = do(
    require_http_method("POST"),
    admin_instance_request,
    json_api_call,
    return_400_if_validation_errors,
    views.update_logo)

green_infrastructure = admin_route(
    GET=do(render_template('manage_treemap/green_infrastructure.html'),
           green_infrastructure_views.site_config_green_infrastructure),
    PUT=json_do(green_infrastructure_views.green_infrastructure),
)

comment_moderation = admin_route(
    GET=do(render_template('manage_treemap/comment_moderation.html'),
           comment_moderation)
)

photo_review_admin = admin_route(
    GET=do(render_template('manage_treemap/photo_review.html'),
           photo_views.photo_review)
)

photo_review = do(
    require_http_method("GET"),
    admin_instance_request,
    render_template('manage_treemap/partials/photo_review.html'),
    photo_views.photo_review)

approve_or_reject_photos = do(
    require_http_method("POST"),
    admin_instance_request,
    render_template('manage_treemap/partials/photo_review.html'),
    photo_views.approve_or_reject_photos)

importer = admin_route(
    GET=do(render_template('manage_treemap/importer.html'),
           list_imports)
)

benefits = admin_route(
    GET=do(render_template('manage_treemap/benefits.html'),
           views.benefits_convs),
    PUT=json_do(views.update_benefits)
)

units = admin_route(
    GET=do(render_template('manage_treemap/units.html'), views.units),
    PUT=json_do(update_instance_fields_with_validator,
                views.units_validator)
)

udfs = do(
    admin_instance_request,
    route(PUT=udf_bulk_update,
          POST=do(
              return_400_if_validation_errors,
              render_template("manage_treemap/partials/fields/udf_row.html"),
              udf_create),
          GET=do(render_template('manage_treemap/udfs.html'),
                 udf_list))
)

udf_change = do(
    admin_instance_request,
    route(
        GET=do(
            render_template(
                "manage_treemap/partials/fields/udf_delete_popup.html"),
            udf_delete_popup),
        PUT=do(return_400_if_validation_errors, udf_update_choice),
        DELETE=udf_delete))

search_config_page = admin_route(
    GET=do(render_template('manage_treemap/search_fields.html'),
           field_views.search_config)
)

search_config = do(
    admin_instance_request,
    route(
        PUT=do(json_api_call,
               return_400_if_validation_errors,
               field_views.set_search_config),
        GET=do(
            render_template(
                'manage_treemap/partials/fields/search_fields.html'),
            field_views.search_config))
)

field_configs = admin_route(
    GET=do(render_template('manage_treemap/field_configuration.html'),
           field_views.set_fields_page)
)

set_field_configs = do(
    admin_instance_request,
    route(
        PUT=do(json_api_call,
               return_400_if_validation_errors,
               field_views.set_fields),
        GET=do(
            render_template(
                'manage_treemap/partials/fields/field_groups.html'),
            field_views.set_fields_page))
)

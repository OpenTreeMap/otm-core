# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import patterns

from opentreemap.util import route

from api.views import (status, version,
                       remove_current_tree_from_plot, add_tree_photo,
                       get_tree_image, plots_endpoint, species_list_endpoint,
                       approve_pending_edit, reject_pending_edit,
                       geocode_address, reset_password, user_endpoint,
                       add_profile_photo, update_password,
                       plot_endpoint, edits, plots_closest_to_point_endpoint,
                       instance_info_endpoint)

from treemap.instance import URL_NAME_PATTERN


instance_pattern = r'^(?P<instance_url_name>' + URL_NAME_PATTERN + r')'

urlpatterns = patterns(
    '',
    (r'^$', status),
    (r'^version$', version),

    (r'^plots/(?P<plot_id>\d+)/tree/photo$', route(POST=add_tree_photo)),
    (r'^plots/(?P<plot_id>\d+)/tree/photo/(?P<photo_id>\d+)', get_tree_image),

    (r'^addresses/(?P<address>.+)', geocode_address),

    (r'^user$', user_endpoint),
    (r'^user/(?P<user_id>\d+)/photo/(?P<title>.+)$', add_profile_photo),
    (r'^user/(?P<user_id>\d+)/password$', update_password),
    (r'^user/(?P<user_id>\d+)/reset_password$', reset_password),
    (r'^user/(?P<user_id>\d+)/edits$', edits),

    (instance_pattern + r'/plots/(?P<plot_id>\d+)/tree$',
     route(DELETE=remove_current_tree_from_plot)),

    (instance_pattern + r'/pending-edits/(?P<pending_edit_id>\d+)/approve',
     route(POST=approve_pending_edit)),

    (instance_pattern + r'/pending-edits/(?P<pending_edit_id>\d+)/reject',
     route(POST=reject_pending_edit)),

    # OTM2/instance endpoints
    (instance_pattern + '$', instance_info_endpoint),
    (instance_pattern + '/species$', species_list_endpoint),
    (instance_pattern + r'/plots$', plots_endpoint),
    (instance_pattern + r'/plots/(?P<plot_id>\d+)$',
     plot_endpoint),
    (instance_pattern + r'/locations/'
     '(?P<lat>-{0,1}\d+(\.\d+){0,1}),(?P<lng>-{0,1}\d+(\.\d+){0,1})'
     '/plots', plots_closest_to_point_endpoint),
)

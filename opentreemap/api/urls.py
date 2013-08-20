from django.conf.urls import patterns
from opentreemap.util import route
from views import (get_plot_list, create_plot_optional_tree, status,
                   version, get_plot, remove_plot,
                   update_plot_and_tree, get_current_tree_from_plot,
                   remove_current_tree_from_plot, add_tree_photo,
                   get_tree_image, plots_closest_to_point,
                   approve_pending_edit, reject_pending_edit, species_list,
                   geocode_address, reset_password, verify_auth,
                   register, add_profile_photo, update_password,
                   recent_edits)

urlpatterns = patterns(
    '',
    (r'^$', status),
    (r'^version$', version),
    (r'^(?P<instance_id>\d+)/plots$',
     route(GET=get_plot_list, POST=create_plot_optional_tree)),

    (r'^(?P<instance_id>\d+)/plots/(?P<plot_id>\d+)$',
     route(GET=get_plot, PUT=update_plot_and_tree, DELETE=remove_plot)),

    (r'^(?P<instance_id>\d+)/plots/(?P<plot_id>\d+)/tree$',
     route(GET=get_current_tree_from_plot,
           DELETE=remove_current_tree_from_plot)),

    (r'^plots/(?P<plot_id>\d+)/tree/photo$', route(POST=add_tree_photo)),
    (r'^plots/(?P<plot_id>\d+)/tree/photo/(?P<photo_id>\d+)', get_tree_image),
    (r'^locations/'
     '(?P<lat>-{0,1}\d+(\.\d+){0,1}),(?P<lon>-{0,1}\d+(\.\d+){0,1})'
     '/plots', plots_closest_to_point),

    (r'^(?P<instance_id>\d+)/pending-edits/(?P<pending_edit_id>\d+)/approve',
     route(POST=approve_pending_edit)),

    (r'^(?P<instance_id>\d+)/pending-edits/(?P<pending_edit_id>\d+)/reject',
     route(POST=reject_pending_edit)),

    (r'^species', species_list),
    (r'^addresses/(?P<address>.+)', geocode_address),

    (r'^login/reset_password$', reset_password),
    (r'^login$', verify_auth),

    (r'^user/$', route(POST=register)),
    (r'^user/(?P<user_id>\d+)/photo/(?P<title>.+)$', add_profile_photo),
    (r'^user/(?P<user_id>\d+)/password$', update_password),
    (r'^user/(?P<user_id>\d+)/edits$', recent_edits),
)

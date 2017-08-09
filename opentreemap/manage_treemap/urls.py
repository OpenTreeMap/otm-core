from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import url

from manage_treemap import routes

urlpatterns = [
    url(r'^$', routes.management, name='management'),
    url(r'^notifications/$', routes.admin_counts, name='admin_counts'),

    url(r'^site-config/$', routes.site_config, name='site_config'),
    url(r'^external-link/$', routes.external_link, name='external_link'),
    url(r'^branding/$', routes.branding, name='branding'),
    url(r'^embed/$', routes.embed, name='embed'),
    url(r'^logo/$', routes.update_logo, name='logo_endpoint'),
    url(r'^green-infrastructure/$', routes.green_infrastructure,
        name='green_infrastructure'),

    url(r'^comment-moderation/$', routes.comment_moderation,
        name='comment_moderation_admin'),

    url(r'^photo-review/$', routes.photo_review_admin,
        name='photo_review_admin'),
    url(r'^photo_review-partial/$', routes.photo_review,
        name='photo_review_partial'),
    url(r'^photo-review/approve-reject/(?P<action>(approve)|(reject))$',
        routes.approve_or_reject_photos, name='approve_or_reject_photos'),

    url(r'^user-roles/$', routes.user_roles, name='user_roles'),
    url(r'^user-roles-partial/$', routes.user_roles_partial,
        name='user_roles_partial'),
    url(r'^user-invite/(?P<invite_id>\d+)$', routes.user_invites,
        name='user_invite'),
    url(r'^roles/$', routes.roles, name='roles_endpoint'),
    url(r'^export/user/(?P<data_format>(csv|json))/$',
        routes.begin_export_users, name='management_begin_export_users'),
    url(r'^clear-udf-notifications/$',
        routes.clear_udf_notifications, name='clear_udf_notifications'),

    url(r'^bulk-uploader/$', routes.importer, name='importer'),
    url(r'^benefits/$', routes.benefits, name='benefits'),
    url(r'^units/$', routes.units, name='units_endpoint'),

    url(r'^udfs/$', routes.udfs, name='udfs'),
    url(r'^udfs/(?P<udf_id>\d+)$', routes.udf_change, name='udfs_change'),
    url(r'^search-configuration/$', routes.search_config_page,
        name='search_config_admin'),
    url(r'^search-configuration-partial/$', routes.search_config,
        name='search_config'),
    url(r'^field-configuration/$', routes.field_configs,
        name='field_configs'),
    url(r'^set-fields/$', routes.set_field_configs,
        name='set_field_configs'),
]

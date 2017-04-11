from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import patterns, url

from manage_treemap import routes

urlpatterns = patterns(
    '',
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

    url(r'^bulk-uploader/$', routes.importer, name='importer'),
    url(r'^benefits/$', routes.benefits, name='benefits'),
)

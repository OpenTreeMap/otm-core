# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import patterns, include, url
from django.conf import settings
from django.views.generic import RedirectView
from django.contrib import admin

from opentreemap.util import route

from treemap.views import (user_view, root_settings_js_view,
                           profile_to_user_view, user_audits_view,
                           instance_not_available_view, update_user_view,
                           unsupported_view, landing_view, scss_view,
                           upload_user_photo_view)
from treemap.instance import URL_NAME_PATTERN
from treemap.urls import USERNAME_PATTERN

from ecobenefits.views import within_itree_regions_view


admin.autodiscover()
instance_pattern = r'^(?P<instance_url_name>' + URL_NAME_PATTERN + r')'


# Testing notes:
# We want to test that every URL succeeds (200) or fails with bad data (404).
# If you add/remove/modify a URL, please update the corresponding test(s).
# For URLs included via <app>.urls, see <app>/tests
# For "top level" URLs defined here, see treemap/tests/urls.py (RootUrlTests)

urlpatterns = patterns(
    '',
    (r'^robots.txt$', RedirectView.as_view(
        url='/static/robots.txt', permanent=True)),
    # Setting permanent=False in case we want to allow customizing favicons
    # per instance in the future
    (r'^favicon\.png$', RedirectView.as_view(
        url='/static/img/favicon.png', permanent=False)),
    url('^comments/', include('django.contrib.comments.urls')),
    url(r'^', include('geocode.urls')),
    url(r'^$', landing_view),
    url(r'^config/settings.js$', root_settings_js_view),
    url(r'^users/%s/$' % USERNAME_PATTERN,
        route(GET=user_view, PUT=update_user_view), name='user'),
    url(r'^users/%s/edits/$' % USERNAME_PATTERN,
        user_audits_view, name='user_audits'),
    url(r'^users/%s/photo/$' % USERNAME_PATTERN,
        upload_user_photo_view, name='user_photo'),
    url(r'^api/v2/', include('api.urls')),
    # The profile view is handled specially by redirecting to
    # the page of the currently logged in user
    url(r'^accounts/profile/$', profile_to_user_view, name='profile'),
    url(r'^accounts/logout/$', 'django.contrib.auth.views.logout',
        {'next_page': '/'}),
    url(r'^accounts/', include('registration_backend.urls')),
    # Create a redirect view for setting the session language preference
    # https://docs.djangoproject.com/en/1.0/topics/i18n/#the-set-language-redirect-view  # NOQA
    url(r'^i18n/', include('django.conf.urls.i18n')),
    url(r'^not-available$', instance_not_available_view,
        name='instance_not_available'),
    url(r'^unsupported$', unsupported_view, name='unsupported'),
    url(r'^main\.css$', scss_view, name='scss'),
    url(r'^eco/benefit/within_itree_regions/$', within_itree_regions_view,
        name='within_itree_regions'),
    url(instance_pattern + r'/', include('treemap.urls')),
    url(instance_pattern + r'/eco/', include('ecobenefits.urls')),
    url(instance_pattern + r'/export/', include('exporter.urls'))
)

if settings.USE_JS_I18N:
    js_i18n_info_dict = {
        'domain': 'djangojs',
        'packages': settings.I18N_APPS,
    }

    urlpatterns = patterns('', url(r'^jsi18n/$',
                           'django.views.i18n.javascript_catalog',
                           js_i18n_info_dict)) + urlpatterns

if settings.EXTRA_URLS:
    for (url_pattern, url_module) in settings.EXTRA_URLS:
        urlpatterns = patterns('', url(url_pattern,
                                       include(url_module))) + urlpatterns

if settings.DEBUG:
    urlpatterns = patterns(
        '', url(r'^admin/', include(admin.site.urls))) + urlpatterns

handler404 = 'treemap.views.error_404_view'
handler500 = 'treemap.views.error_500_view'
# Not hooked up yet
handler503 = 'treemap.views.error_503_view'

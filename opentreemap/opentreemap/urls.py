# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import patterns, include, url
from django.conf import settings
from django.views.generic import RedirectView
from django.contrib import admin

from django.shortcuts import redirect

from treemap import routes
from treemap.instance import URL_NAME_PATTERN
from treemap.urls import USERNAME_PATTERN
from treemap.ecobenefits import within_itree_regions_view

from registration_backend.views import RegistrationView


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
    url('^comments/', include('django_comments.urls')),
    url(r'^', include('geocode.urls')),
    url(r'^stormwater/', include('stormwater.urls')),
    # Default hardcoded front site. #TODO: PG make this more pretty.
    url(r'^$', RedirectView.as_view(url='/warszawa/map/')),
    # url(r'^$', routes.landing_page),
    url(r'^config/settings.js$', routes.root_settings_js),
    url(r'^users/%s/$' % USERNAME_PATTERN,
        routes.user, name='user'),
    url(r'^users/%s/edits/$' % USERNAME_PATTERN,
        routes.user_audits, name='user_audits'),
    url(r'^users/%s/photo/$' % USERNAME_PATTERN,
        routes.upload_user_photo, name='user_photo'),
    url(r'^api/v(?P<version>\d+)/', include('api.urls')),
    # The profile view is handled specially by redirecting to
    # the page of the currently logged in user
    url(r'^accounts/profile/$', routes.profile_to_user_page, name='profile'),
    url(r'^accounts/logout/$', 'django.contrib.auth.views.logout',
        {'next_page': '/warszawa/map/'}), #TODO: PG make this more pretty
    url(r'^accounts/forgot-username/$', routes.forgot_username,
        name='forgot_username'),
    url(r'^accounts/', include('registration_backend.urls')),
    # Create a redirect view for setting the session language preference
    # https://docs.djangoproject.com/en/1.0/topics/i18n/#the-set-language-redirect-view  # NOQA
    url(r'^i18n/', include('django.conf.urls.i18n')),
    url(r'^not-available$', routes.instance_not_available,
        name='instance_not_available'),
    url(r'^unsupported$', routes.unsupported_page, name='unsupported'),
    url(r'^main\.css$', routes.compile_scss, name='scss'),
    url(r'^eco/benefit/within_itree_regions/$', within_itree_regions_view,
        name='within_itree_regions'),
    url(r'^instances/$', routes.instances_geojson),
    url(instance_pattern + r'/accounts/register/$',
        RegistrationView.as_view(),
       name='instance_registration_register'),
    url(instance_pattern + r'/', include('treemap.urls')),
    url(instance_pattern + r'/importer/', include('importer.urls',
                                                  namespace='importer')),
    url(instance_pattern + r'/export/', include('exporter.urls')),
    url(instance_pattern + r'/comments/', include('otm_comments.urls')),
)

if settings.USE_JS_I18N:
    js_i18n_info_dict = {
        'domain': 'djangojs',
        'packages': settings.I18N_APPS,
    }

    urlpatterns = patterns(
        '', url(r'^jsi18n/$', 'django.views.i18n.javascript_catalog',
                js_i18n_info_dict)
    ) + urlpatterns

if settings.EXTRA_URLS:
    for (url_pattern, url_module) in settings.EXTRA_URLS:
        urlpatterns = patterns('', url(url_pattern,
                                       include(url_module))) + urlpatterns

if settings.DEBUG:
    urlpatterns = patterns(
        '', url(r'^admin/', include(admin.site.urls))) + urlpatterns

handler404 = 'treemap.routes.error_404_page'
handler500 = 'treemap.routes.error_500_page'
# Not hooked up yet
handler503 = 'treemap.routes.error_503_page'

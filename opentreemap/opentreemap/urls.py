# -*- coding: utf-8 -*-


from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.views.generic import RedirectView
from django.views.i18n import JavaScriptCatalog

from treemap import routes
from treemap.ecobenefits import within_itree_regions_view
from treemap.instance import URL_NAME_PATTERN
from treemap.urls import USERNAME_PATTERN

from registration_backend.views import RegistrationView


admin.autodiscover()
instance_pattern = r'^(?P<instance_url_name>' + URL_NAME_PATTERN + r')'


# Testing notes:
# We want to test that every URL succeeds (200) or fails with bad data (404).
# If you add/remove/modify a URL, please update the corresponding test(s).
# For URLs included via <app>.urls, see <app>/tests
# For "top level" URLs defined here, see treemap/tests/urls.py (RootUrlTests)

root_url = []
if hasattr(settings, 'DEFAULT_INSTANCE') and settings.DEFAULT_INSTANCE:
    root_url.append(url(r'^$', RedirectView.as_view(url='/{}/ui/'.format(settings.DEFAULT_INSTANCE))))
else:
    root_url.append(url(r'^$', routes.landing_page))

urlpatterns = root_url + [
    url(r'^robots.txt$', RedirectView.as_view(
        url='/static/robots.txt', permanent=True)),
    # Setting permanent=False in case we want to allow customizing favicons
    # per instance in the future
    url(r'^favicon\.png$', RedirectView.as_view(
        url='/static/img/favicon.png', permanent=False)),
    url('^comments/', include('django_comments.urls')),
    url(r'^', include('geocode.urls')),
    url(r'^stormwater/', include('stormwater.urls')),
    #url(r'^$', routes.landing_page),
    url(r'^config/settings.js$', routes.root_settings_js),
    url(r'^users/%s/$' % USERNAME_PATTERN,
        routes.user, name='user'),
    url(r'^users/%s/edits/$' % USERNAME_PATTERN,
        routes.user_audits, name='user_audits'),
    #url(r'^users/%s/photo/$' % USERNAME_PATTERN,
    #    routes.upload_user_photo, name='user_photo'),
    url(r'^api/v(?P<version>\d+)/', include('api.urls')),
    # The profile view is handled specially by redirecting to
    # the page of the currently logged in user
    url(r'^accounts/profile/$', routes.profile_to_user_page, name='profile'),
    url(r'^accounts/logout/$', LogoutView.as_view(), name='logout'),
    url(r'^accounts/forgot-username/$', routes.forgot_username,
        name='forgot_username'),
    url(r'^accounts/resend-activation-email/$', routes.resend_activation_email,
        name='resend_activation_email'),
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
    url(r'^anonymous-boundary/$',
        routes.anonymous_boundary, name='anonymous_boundary'),
    url(instance_pattern + r'/accounts/register/$',
        RegistrationView.as_view(),
        name='instance_registration_register'),
    url(instance_pattern + r'/ui/', include('frontend.urls')),
    url(instance_pattern + r'/', include('treemap.urls')),
    url(instance_pattern + r'/importer/', include(('importer.urls', 'importer'),
                                                  namespace='importer')),
    url(instance_pattern + r'/export/', include('exporter.urls')),
    url(instance_pattern + r'/comments/', include('otm_comments.urls')),
    url(instance_pattern + r'/management/', include('manage_treemap.urls')),
    url(r'', include('modeling.urls')),
]


if settings.USE_JS_I18N:
    js_i18n_info_dict = {
        'domain': 'djangojs',
        'packages': settings.I18N_APPS,
    }

    urlpatterns = [
        url(r'^jsi18n/$', JavaScriptCatalog, js_i18n_info_dict)
    ] + urlpatterns

if settings.EXTRA_URLS:
    urlpatterns = [
        url(url_pattern, include(url_module))
        for (url_pattern, url_module) in settings.EXTRA_URLS
    ] + urlpatterns

if settings.DEBUG:
    urlpatterns = [url(r'^admin/', admin.site.urls)] + urlpatterns

handler404 = 'treemap.routes.error_404_page'
handler500 = 'treemap.routes.error_500_page'
# Not hooked up yet
handler503 = 'treemap.routes.error_503_page'

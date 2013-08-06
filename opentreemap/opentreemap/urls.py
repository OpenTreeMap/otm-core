from django.conf.urls import patterns, include, url
from django.conf import settings
from django.views.generic import RedirectView

from treemap.views import (user_view, root_settings_js_view,
                           profile_to_user_view)

from django.contrib import admin
admin.autodiscover()

js_i18n_info_dict = {
    'domain': 'djangojs',
    'packages': settings.I18N_APPS,
}

urlpatterns = patterns(
    '',
    # Setting permanent=False in case we want to allow customizing favicons
    # per instance in the future
    (r'^favicon\.ico$', RedirectView.as_view(
        url='/static/img/favicon.ico', permanent=False)),
    url(r'^', include('geocode.urls')),
    url(r'^(?P<instance_id>\d+)/', include('treemap.urls')),
    url(r'^(?P<instance_id>\d+)/eco/', include('ecobenefits.urls')),
    url(r'^config/settings.js$', root_settings_js_view),
    url(r'^users/(?P<username>\w+)/', user_view),
    url(r'^api/v2/', include('api.urls')),
    # The profile view is handled specially by redirecting to
    # the page of the currently logged in user
    url(r'^accounts/profile/$', profile_to_user_view, name='profile'),
    url(r'^accounts/', include('registration_backend.urls')),
    # Create a redirect view for setting the session language preference
    # https://docs.djangoproject.com/en/1.0/topics/i18n/#the-set-language-redirect-view  # NOQA
    url(r'^i18n/', include('django.conf.urls.i18n')),
    url(r'^jsi18n/$', 'django.views.i18n.javascript_catalog',
        js_i18n_info_dict),
)

if settings.DEBUG:
    urlpatterns += patterns('', url(r'^admin/', include(admin.site.urls)))

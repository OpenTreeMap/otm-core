from django.conf.urls import patterns, include, url
from django.conf import settings
from django.views.generic import RedirectView

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns(
    '',
    # Setting permanent=False in case we want to allow customizing favicons
    # per instance in the future
    (r'^favicon\.ico$', RedirectView.as_view(
        url='/static/img/favicon.ico', permanent=False)),
    url(r'^', include('geocode.urls')),
    url(r'^(?P<instance_id>\d+)/', include('treemap.urls')),
    url(r'^(?P<instance_id>\d+)/eco/', include('ecobenefits.urls')),
    url(r'^api/v2/', include('api.urls')),
    url(r'^accounts/', include('registration_backend.urls')),
)

if settings.DEBUG:
    urlpatterns += patterns('', url(r'^admin/', include(admin.site.urls)))

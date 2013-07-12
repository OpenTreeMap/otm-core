from django.conf.urls import patterns, include, url
from django.conf import settings

from django.contrib import admin
admin.autodiscover()

from treemap.views import index, settings

urlpatterns = patterns(
    '',

    url(r'^', include('geocode.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'(?P<instance_id>\d+)/', include('treemap.urls')),
    url(r'(?P<instance_id>\d+)/eco/', include('ecobenefits.urls')),
)

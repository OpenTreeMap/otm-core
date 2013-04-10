from django.conf.urls import patterns, include, url
from example.views import index

from django.contrib import admin
admin.autodiscover()

from treemap.views import index, settings
import treemap

urlpatterns = patterns(
    '',

    url(r'^admin/', include(admin.site.urls)),
    url(r'(?P<instance_id>\d+)/', include('treemap.urls')),
    url(r'(?P<instance_id>\d+)/eco/', include('ecobenefits.urls')),
)

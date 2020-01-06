

from django.conf.urls import url

from exporter.views import begin_export_endpoint, check_export_endpoint

urlpatterns = [
    url(r'(?P<model>(tree|species))/$',
        begin_export_endpoint, name='begin_export'),
    url(r'check/(?P<job_id>\d+)/$',
        check_export_endpoint, name='check_export'),
]

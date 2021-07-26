from django.conf.urls import url
from treemap.urls import USERNAME_PATTERN

from . import views

urlpatterns = [
    #url('', render_template('frontend/index.html')()),
    #url('', views.index_page),
    url(r'^$', views.react_map_page, name='react_map_index'),
    url(r'^map/$', views.react_map_page, name='react_map'),
    url(r'^user-dashboard/$', views.user_dashboard, name='user_dashboard'),
]

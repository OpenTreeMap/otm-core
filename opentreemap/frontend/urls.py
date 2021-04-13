from django.conf.urls import url
from . import views

urlpatterns = [
    #url('', render_template('frontend/index.html')()),
    #url('', views.index_page),
    url(r'^$', views.react_map_page, name='react_map_index'),
    url(r'^map/$', views.react_map_page, name='react_map'),
]

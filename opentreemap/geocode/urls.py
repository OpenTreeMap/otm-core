



from django.conf.urls import url
from geocode.views import geocode_view, get_esri_token_view

urlpatterns = [
    url(r'^geocode$', geocode_view, name='geocode'),
    url(r'^get-geocode-token$', get_esri_token_view, name='get_geocode_token')
]

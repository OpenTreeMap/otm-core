# -*- coding: utf-8 -*-




from django_tinsel.decorators import json_api_call, route
from django_tinsel.utils import decorate as do

from treemap.decorators import instance_request

from stormwater import views


polygon_for_point = route(GET=do(
    instance_request, json_api_call, views.polygon_for_point))

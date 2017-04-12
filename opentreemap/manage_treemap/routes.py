# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from functools import partial

from django_tinsel.decorators import route, render_template, json_api_call
from django_tinsel.utils import decorate as do

from treemap.decorators import (require_http_method, admin_instance_request,
                                return_400_if_validation_errors)

from manage_treemap import views


admin_route = lambda **kwargs: admin_instance_request(route(**kwargs))

json_do = partial(do, json_api_call, return_400_if_validation_errors)

management = do(
    require_http_method('GET'),
    views.management_root)

admin_counts = admin_route(
    GET=do(json_api_call, views.admin_counts)
)

benefits = admin_route(
    GET=do(render_template('manage_treemap/benefits.html'),
           views.benefits_convs),
    PUT=json_do(views.update_benefits)
)

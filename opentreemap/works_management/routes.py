# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from functools import partial

from django_tinsel.utils import decorate as do
from django_tinsel.decorators import render_template

from treemap.decorators import (instance_request, requires_feature,
                                requires_permission, require_http_method)
from treemap.instance import PERMISSION_ACCESS_WORKS_MANAGEMENT

from works_management import views


def works_management_instance_request(view_fn, redirect=True):
    return do(
        partial(instance_request, redirect=redirect),
        requires_feature('works_management'),
        requires_permission(PERMISSION_ACCESS_WORKS_MANAGEMENT),
        view_fn)


work_orders = do(
    works_management_instance_request,
    require_http_method('GET'),
    render_template('works_management/work_orders.html'),
    views.work_orders)

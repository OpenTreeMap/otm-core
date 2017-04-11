# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django_tinsel.utils import decorate as do

from treemap.decorators import require_http_method

from manage_treemap import views


management = do(
    require_http_method('GET'),
    views.management_root)

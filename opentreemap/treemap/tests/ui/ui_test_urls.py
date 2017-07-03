# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.conf.urls import include, url
from django.http import HttpResponse

from opentreemap import urls

testing_id = 1


def full_utf8_grid(request):
    """
    Creates a big utf8 grid where every entry is 'turned on'
    to point to whatever plot id is the currently assigned value
    of testing_id

    this is useful for mocking a tiler utf8 grid response so
    that ui tests can click the map and simulate clicking a
    rendered tree tile.
    """
    global testing_id

    quoted_space_line = '"' + (' ' * 64) + '"'
    quoted_space_line_with_comma = quoted_space_line + ','

    full_space_utf8_grid = ('{"grid":[' +
                            (quoted_space_line_with_comma * 63) +
                            quoted_space_line +
                            '],"keys":["1"],"data":{"1":{"id":%s}}}'
                            % testing_id)

    response = HttpResponse(full_space_utf8_grid)
    response['Content-Type'] = 'application/json'
    return response


urlpatterns = [
    url(r'^tile/.*', full_utf8_grid),
    url(r'', include(urls))
]

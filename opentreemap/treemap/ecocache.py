# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
import hashlib

from django.conf import settings
from django.core.cache import cache

from treemap.models import Plot

# Cache the results of plot counts and tree ecobenefit summary requests.
#
# Plot key is count/plots/<url_name>/<geo_rev>/<filter_hash>
# Eco key is eco/trees/<url_name>/<eco_rev>/<filter_hash>
#
# In the case of ecobenefit summary requests from searches:
#
# Plot key is count/plots/<url_name>/<universal_rev>/<filter_hash>
# Eco key is eco/trees/<url_name>/<universal_rev>/<filter_hash>

# Entries will be neither numerous nor large, so let them live for a month
_TIMEOUT = 60 * 60 * 24 * 30


def get_cached_tree_benefits(filter, compute_value):
    prefix = 'eco/trees'
    return _get_or_compute(prefix, filter, compute_value)


def get_cached_plot_count(filter):
    prefix = 'count/plots'
    compute_value = lambda: filter.get_object_count(Plot)

    return _get_or_compute(prefix, filter, compute_value)


def _get_or_compute(prefix, filter, compute_value):
    if not settings.USE_ECO_CACHE:
        value = compute_value()
    else:
        key = _get_key(prefix, filter)
        value = cache.get(key)
        if value is None:
            value = compute_value()
            cache.set(key, value, _TIMEOUT)
    return value


def _get_key(prefix, filter):
    if filter and (filter.filterstr or filter.displaystr):
        version = filter.instance.universal_rev
    elif prefix == 'eco/trees':
        version = filter.instance.eco_rev
    elif prefix == 'count/plots':
        version = filter.instance.geo_rev
    else:
        raise ValueError()
    filter_key = '%s/%s' % (filter.filterstr, filter.displaystr)
    filter_hash = hashlib.md5(filter_key).hexdigest()
    key = "%s/%s/%s/%s" % (prefix,
                           filter.instance.url_name,
                           version,
                           filter_hash)
    return key

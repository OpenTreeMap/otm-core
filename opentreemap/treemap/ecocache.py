# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
import hashlib

from django.conf import settings
from django.core.cache import cache

# Cache the results of plot counts and tree ecobenefit summary searches.
# Plot key is count/plots/<url_name>/<geo_rev>/<filter_hash>
# Eco key is eco/trees/<url_name>/<eco_rev>/<filter_hash>

# Entries will be neither numerous nor large, so let them live for a month
_TIMEOUT = 60 * 60 * 24 * 30


def get_cached_tree_benefits(filter, compute_value):
    prefix = 'eco/trees'
    version = filter.instance.eco_rev
    return _get_or_compute(prefix, version, filter, compute_value)


def get_cached_plot_count(filter, compute_value):
    prefix = 'count/plots'
    version = filter.instance.geo_rev
    return _get_or_compute(prefix, version, filter, compute_value)


def _get_or_compute(prefix, version, filter, compute_value):
    if not settings.USE_ECO_CACHE:
        return None
    key = _get_key(prefix, version, filter)
    value = cache.get(key)
    if not value:
        value = compute_value()
        cache.set(key, value, _TIMEOUT)
    return value


def _get_key(prefix, version, filter):
    filter_key = '%s/%s' % (filter.filterstr, filter.displaystr)
    filter_hash = hashlib.md5(filter_key).hexdigest()
    key = "%s/%s/%s/%s" % (prefix,
                           filter.instance.url_name,
                           version,
                           filter_hash)
    return key

# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
import hashlib

from django.conf import settings
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete

from treemap.models import Plot, ITreeCodeOverride

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


def get_cached_benefits(class_name, filter, compute_value):
    prefix = 'eco/%s' % class_name
    return _get_or_compute(prefix, filter, compute_value)


def get_cached_plot_count(filter):
    prefix = 'count/Plot'
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
        # Example of why eco_rev is insufficient when a filter is active:
        # You filter for only trees taller than 30 ft. We compute and cache
        # benefits for your 25 tall trees. Now you update the height field of
        # a tree from 28 to 32 ft. That doesn't change the eco_rev, so we
        # incorrectly display the cached value instead of recomputing eco
        # for your now 26 tall trees. Your update does change the
        # universal_rev however, so using that in the cache key solves the
        # problem.
        version = filter.instance.universal_rev
    elif prefix == 'eco/Plot':
        version = filter.instance.eco_rev
    elif prefix == 'count/Plot':
        version = filter.instance.geo_rev
    else:
        # We are computing benefits for features other than trees
        version = filter.instance.universal_rev

    filter_key = '%s/%s' % (filter.filterstr, filter.displaystr)
    # Explicitly calling `encode()` ensures that the presence of a
    # unicode symbol in the filter string will not raise a
    # UnicodeEncodeError exception when calling `md5()`
    filter_hash = hashlib.md5(filter_key.encode('utf-8')).hexdigest()
    key = "%s/%s/%s/%s" % (prefix,
                           filter.instance.url_name,
                           version,
                           filter_hash)
    return key


# ----------------------------------------------------------------
# The ecoservice keeps a cache of i-Tree code overrides.
# Store a cache buster in Redis, and keep a local copy.
# If the local copy is stale, invalidate the cache of the local ecoservice.

_ITREE_CODE_OVERRIDE_REV_KEY = 'itree_code_override_rev'
my_itree_code_override_rev = None


def _increment_itree_code_override_rev(*args, **kwargs):
    _init_if_needed()
    cache.incr(_ITREE_CODE_OVERRIDE_REV_KEY)


def invalidate_ecoservice_cache_if_stale():
    from treemap import ecobackend
    global my_itree_code_override_rev

    cached_rev = _init_if_needed()

    if my_itree_code_override_rev != cached_rev:
        __, err = ecobackend.json_benefits_call('invalidate_cache', {})
        if err:
            raise Exception('Failed to invalidate ecoservice cache')
        my_itree_code_override_rev = cached_rev


def _init_if_needed():
    global my_itree_code_override_rev

    cached_rev = cache.get(_ITREE_CODE_OVERRIDE_REV_KEY)
    if cached_rev is None:
        timeout = 60 * 60 * 24 * 365 * 10  # 10 years
        cache.set(_ITREE_CODE_OVERRIDE_REV_KEY, 1, timeout)
        cached_rev = 1

    if my_itree_code_override_rev is None:
        my_itree_code_override_rev = cached_rev

    return cached_rev


post_save.connect(_increment_itree_code_override_rev, sender=ITreeCodeOverride)
post_delete.connect(_increment_itree_code_override_rev,
                    sender=ITreeCodeOverride)

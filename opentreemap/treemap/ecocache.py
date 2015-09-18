# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
import hashlib

from django.conf import settings
from django.core.cache import cache

# Cache the results of tree ecobenefit summary searches.
# Cache key is eco/trees/<url_name>/<eco_rev>/<filter_string>/<display_string>

# Entries will be neither numerous nor large, so let them live for a month
TIMEOUT = 60 * 60 * 24 * 30


def get_cached_benefits(instance, filter):
    if settings.USE_ECO_CACHE:
        key = _get_key(instance, filter)
        benefits = cache.get(key)
        return benefits
    else:
        return None


def cache_benefits(instance, filter, benefits):
    if settings.USE_ECO_CACHE:
        key = _get_key(instance, filter)
        cache.set(key, benefits, TIMEOUT)


def _get_key(instance, filter):
    filter_key = '%s/%s' % (filter.filterstr, filter.displaystr)
    filter_hash = hashlib.md5(filter_key).hexdigest()
    key = "eco/trees/%s/%s/%s" % (instance.url_name,
                                  instance.eco_rev,
                                  filter_hash)
    return key

# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division


def _clean_string(s):
    s = s.strip()
    if not isinstance(s, unicode):
        s = unicode(s, 'utf-8')
    return s


def lowerkeys(h):
    h2 = {}
    for (k, v) in h.iteritems():
        k = k.lower().strip()
        if k != 'ignore':
            if isinstance(v, basestring):
                v = _clean_string(v)

            h2[k] = v

    return h2

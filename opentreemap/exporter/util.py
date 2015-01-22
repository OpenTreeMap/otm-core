# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.templatetags.l10n import localize


# https://github.com/azavea/django-queryset-csv/blob/
# master/djqscsv/djqscsv.py#L123
def sanitize_unicode_record(record):

    def _sanitize_value(value):
        if isinstance(val, unicode):
            return value.encode("utf-8")
        else:
            return localize(value)

    obj = {}
    for key, val in record.iteritems():
        if val:
            obj[_sanitize_value(key)] = _sanitize_value(val)

    return obj

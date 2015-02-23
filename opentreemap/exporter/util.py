# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division


# https://github.com/azavea/django-queryset-csv/blob/
# master/djqscsv/djqscsv.py#L123
def sanitize_unicode_record(record):

    def _sanitize_value(value):
        # make sure every text value is of type 'str', coercing unicode
        if isinstance(value, unicode):
            return value.encode("utf-8")
        elif isinstance(value, str):
            return value
        else:
            return str(value).encode("utf-8")

    obj = {}
    for key, val in record.iteritems():
        if val:
            obj[_sanitize_value(key)] = _sanitize_value(val)

    return obj

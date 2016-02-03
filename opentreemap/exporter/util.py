# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division


def sanitize_unicode_value(value):
    # make sure every text value is of type 'str', coercing unicode
    if isinstance(value, unicode):
        return value.encode("utf-8")
    elif isinstance(value, str):
        return value
    else:
        return str(value).encode("utf-8")


# originally copied from, but now divergent from:
# https://github.com/azavea/django-queryset-csv/blob/
# master/djqscsv/djqscsv.py#L123
def sanitize_unicode_record(record):
    obj = type(record)()
    for key, val in record.iteritems():
        if val:
            obj[sanitize_unicode_value(key)] = sanitize_unicode_value(val)

    return obj

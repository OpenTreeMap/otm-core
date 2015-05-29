# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import codecs
import csv


def _clean_string(s):
    s = s.strip()
    if not isinstance(s, unicode):
        s = unicode(s, 'utf-8')
    return s


def clean_row_data(h):
    h2 = {}
    for (k, v) in h.iteritems():
        k = clean_field_name(k)
        if k != 'ignore':
            if isinstance(v, basestring):
                v = _clean_string(v)

            h2[k] = v

    return h2


def clean_field_name(name):
    return name.lower().strip()


def _as_utf8(f):
    return codecs.EncodedFile(f, 'utf-8')


def _guess_dialect_and_reset_read_pointer(f):
    dialect = csv.Sniffer().sniff(_as_utf8(f).read(4096))
    f.seek(0)
    return dialect


def utf8_file_to_csv_dictreader(f):
    dialect = _guess_dialect_and_reset_read_pointer(f)
    return csv.DictReader(_as_utf8(f),
                          dialect=dialect)

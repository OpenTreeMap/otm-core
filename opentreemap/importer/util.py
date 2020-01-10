# -*- coding: utf-8 -*-


import codecs
import csv


def _clean_string(s):
    s = s.strip()
    if not isinstance(s, str):
        s = str(s, 'utf-8')
    return s


def clean_row_data(h):
    h2 = {}
    for (k, v) in h.items():
        k = clean_field_name(k)
        if k != 'ignore':
            if isinstance(v, str):
                v = _clean_string(v)

            h2[k] = v

    return h2


def clean_field_name(name):
    return name.lower().strip()


def _as_utf8(f):
    return codecs.EncodedFile(f, 'utf-8')


def _guess_dialect_and_reset_read_pointer(f):
    dialect = csv.Sniffer().sniff(_as_utf8(f).read(4096), delimiters=',\t')
    f.seek(0)
    return dialect


def utf8_file_to_csv_dictreader(f):
    dialect = _guess_dialect_and_reset_read_pointer(f)
    # csv.Sniffer does not automatically detect when a file uses the
    # CSV standard "" to escape a double quote. Excel and LibreOffice
    # use this escape by default when saving as CSV.
    dialect.doublequote = True
    return csv.DictReader(_as_utf8(f),
                          dialect=dialect)

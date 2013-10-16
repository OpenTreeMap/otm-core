import csv
import datetime
from django.core.exceptions import ValidationError
from django.db.models.query import ValuesQuerySet
from django.utils.text import slugify
from django.http import HttpResponse
from tempfile import TemporaryFile
""" A simple python package for turning django models into csvs """


def make_csv_response(queryset,
                      filename=None,
                      append_timestamp=False):
    response = _make_empty_csv_response(filename=filename,
                                        append_timestamp=False)
    _write_csv_data(queryset, response)
    return response


def make_csv_file(queryset,
                  filename=None,
                  append_timestamp=False):
    csv_file = TemporaryFile()
    _write_csv_data(queryset, csv_file)
    return csv_file


def _write_csv_data(qs, obj):
    writer = csv.DictWriter(obj, _get_header_row_from_queryset(qs))
    writer.writeheader()
    for record in qs:
        record = _sanitize_unicode_record(record)
        writer.writerow(record)


def _sanitize_unicode_record(record):
    obj = {}
    for key, val in record.iteritems():
        if val:
            if isinstance(val, unicode):
                newval = val.encode("utf-8")
            else:
                newval = str(val)
            obj[key] = newval
    return obj


########################################
# queryset reader functions
########################################

class CSVException(Exception):
    pass


def _get_header_row_from_queryset(qs):
    if type(qs) is ValuesQuerySet:
        return qs.field_names
    try:
        return next(qs.iterator()).keys()
    except StopIteration:
        raise CSVException("Empty queryset provided to exporter.")


def generate_filename(queryset):
    """
    Takes a queryset and returns a default
    base filename based on the underlying data
    """
    return slugify(unicode(queryset.model.__name__)) + "_export.csv"


########################################
# filename/response utility functions
########################################

def _make_empty_csv_response(filename=None, append_timestamp=False):
    # if filename not passed, build one from the queryset underlying class
    if not filename:
        filename = generate_filename(filename)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; %s;' % filename
    response['Cache-Control'] = 'no-cache'

    return response


def _validate_and_clean_filename(filename):

    if filename.count('.'):
        if not filename.endswith('.csv'):
            raise ValidationError('the only accepted file extension is .csv')
        else:
            filename = filename[:-4]

    filename = slugify(filename)
    return filename


def _timestamp_filename(filename):
    if filename != _validate_and_clean_filename:
        raise ValidationError('cannot timestamp unvalidated filename')

    formatted_datestring = datetime.date.today().strftime("%Y%m%d")
    return '%s_%s' % (filename, formatted_datestring)

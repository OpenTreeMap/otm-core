# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json
from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.contrib.gis.db import models
from django.utils.translation import ugettext as _
from django.utils.timezone import now

from treemap.models import User, Instance

from importer import errors


class GenericImportEvent(models.Model):

    class Meta:
        abstract = True

    PENDING_VERIFICATION = 1
    LOADING = 7
    PREPARING_VERIFICATION = 9
    VERIFIYING = 2
    FINISHED_VERIFICATION = 3
    CREATING = 4
    FINISHED_CREATING = 5
    FAILED_FILE_VERIFICATION = 6
    CANCELED = 8
    VERIFICATION_ERROR = 10

    schema_version = models.IntegerField(null=True, blank=True)

    # Original Name of the file
    file_name = models.CharField(max_length=255)

    # Global errors and notices (json)
    errors = models.TextField(default='')

    field_order = models.TextField(default='')

    # Metadata about this particular import
    owner = models.ForeignKey(User)
    instance = models.ForeignKey(Instance)
    created = models.DateTimeField(auto_now=True)
    completed = models.DateTimeField(null=True, blank=True)

    status = models.IntegerField(default=PENDING_VERIFICATION)

    last_processed_at = models.DateTimeField(null=True, blank=True)
    is_lost = models.BooleanField(default=False)

    # The id of a running verification task.  Used for canceling imports
    task_id = models.CharField(max_length=50, default='', blank=True)

    def save(self, *args, **kwargs):
        if self.pk is None:
            # Record current import schema version (defined in subclass)
            self.schema_version = self.import_schema_version
        super(GenericImportEvent, self).save(*args, **kwargs)

    @property
    def row_count(self):
        return self.rows().count()

    def status_summary(self):
        t = "Unknown Error While %s" if self.is_lost else "%s"
        return t % self.status_description()

    def is_past_verifying_stage(self):
        return self.status in {
            GenericImportEvent.FINISHED_VERIFICATION,
            GenericImportEvent.CREATING,
            GenericImportEvent.FINISHED_CREATING,
            GenericImportEvent.FAILED_FILE_VERIFICATION,
            GenericImportEvent.CANCELED,
            GenericImportEvent.VERIFICATION_ERROR
        }

    def status_description(self):
        summaries = {
            self.PENDING_VERIFICATION: "Not Yet Started",
            self.LOADING: "Loading",
            self.PREPARING_VERIFICATION: "Preparing Verification",
            self.VERIFIYING: "Verifying",
            self.FINISHED_VERIFICATION: "Verification Complete",
            self.CREATING: "Creating Trees",
            self.FAILED_FILE_VERIFICATION: "Invalid File Structure",
            self.CANCELED: "Canceled",
            self.VERIFICATION_ERROR: "Verification Error",
        }
        return summaries.get(self.status, "Finished")

    def is_loading(self):
        return self.status == self.LOADING

    def is_running(self):
        return (
            self.status == self.VERIFIYING or
            self.status == self.CREATING)

    def is_finished(self):
        return (
            self.status == self.FINISHED_VERIFICATION or
            self.status == self.FINISHED_CREATING or
            self.status == self.FAILED_FILE_VERIFICATION or
            self.status == self.CANCELED or
            self.status == self.VERIFICATION_ERROR)

    def can_export(self):
        return (not self.is_running()
                and self.has_current_schema_version()
                and self.status != self.FAILED_FILE_VERIFICATION
                and self.status != self.VERIFICATION_ERROR)

    def can_cancel(self):
        return self.status == self.LOADING or self.status == self.VERIFIYING

    def can_add_to_map(self):
        return self.has_current_schema_version() and (
            self.status == self.FINISHED_VERIFICATION or
            self.status == self.FINISHED_CREATING)

    def has_current_schema_version(self):
        return self.schema_version == self.import_schema_version

    def completed_row_summary(self):
        waiting = self.row_set().filter(status=GenericImportRow.WAITING)
        row_count = self.row_count
        n_complete = row_count - waiting.count()
        return '{:,} / {:,}'.format(n_complete, row_count)

    def update_status(self):
        """ Update the status field based on current row statuses """
        pass

    def append_error(self, err, data=None):
        code, msg, fatal = err

        if data and not isinstance(data, list):
            raise ValidationError(_("For this class, data must be a list"))

        if self.errors is None or self.errors == '':
            self.errors = '[]'

        self.errors = json.dumps(
            self._errors_as_array() + [
                {'code': code,
                 'data': data,
                 'fatal': fatal}])

        return self

    def _errors_as_array(self):
        if self.errors is None or self.errors == '':
            return []
        else:
            return json.loads(self.errors)

    def errors_array_with_messages(self):
        errs = self._errors_as_array()
        for error in errs:
            error['msg'] = errors.get_message(error['code'])
        return errs

    def has_errors(self):
        return len(self._errors_as_array()) > 0

    def has_error(self, error):
        code, msg, fatal = error
        error_codes = {e['code'] for e in self._errors_as_array()}
        return code in error_codes

    def row_set(self):
        raise Exception('Abstract Method')

    def rows(self):
        return self.row_set().order_by('idx').all()

    def legal_and_required_fields(self):
        raise Exception('Abstract Method')

    def legal_and_required_fields_title_case(self):
        raise Exception('Abstract Method')

    def ignored_fields(self):
        raise Exception('Abstract Method')

    def validate_field_names(self, input_fields):
        """
        Make sure the imported file has valid columns
        """
        is_valid = True

        legal_fields, required_fields = self.legal_and_required_fields()

        # Extra input fields cause a fatal error
        extra = [field for field in input_fields
                 if field not in legal_fields]
        if len(extra) > 0:
            is_valid = False
            self.append_error(errors.UNMATCHED_FIELDS, list(extra))

        for field in required_fields:
            if field not in input_fields:
                is_valid = False
                self.append_error(errors.MISSING_FIELD, data=[field])

        return is_valid

    def mark_finished_and_save(self):
        self.task_id = ''
        self.last_processed_at = None
        self.save()

    def update_progress_timestamp_and_save(self):
        self.last_processed_at = now()
        self.save()

    def has_not_been_processed_recently(self):
        thirty_ago = now() - timedelta(minutes=30)
        return self.last_processed_at and self.last_processed_at < thirty_ago


class GenericImportRow(models.Model):
    """
    A row of data and import status
    Subclassed by 'Tree Import Row' and 'Species Import Row'
    """

    class Meta:
        abstract = True

    # JSON dictionary from header <-> rows
    data = models.TextField()

    # Row index from original file
    idx = models.IntegerField()

    finished = models.BooleanField(default=False)

    # JSON field containing error information
    errors = models.TextField(default='')

    # Status
    SUCCESS = 0
    ERROR = 1
    WARNING = 2
    WAITING = 3
    VERIFIED = 4

    status = models.IntegerField(default=WAITING)

    def __init__(self, *args, **kwargs):
        super(GenericImportRow, self).__init__(*args, **kwargs)
        self.jsondata = None
        self.cleaned = {}

    @property
    def model_fields(self):
        raise Exception('Abstract Method')

    @property
    def datadict(self):
        if self.jsondata is None:
            self.jsondata = json.loads(self.data)

        return self.jsondata

    @datadict.setter
    def datadict(self, v):
        self.jsondata = v
        self.data = json.dumps(self.jsondata)

    def _errors_as_array(self):
        if self.errors is None or self.errors == '':
            return []
        else:
            return json.loads(self.errors)

    def errors_array_with_messages(self):
        errs = self._errors_as_array()
        for error in errs:
            error['msg'] = errors.get_message(error['code'])
        return errs

    def errors_array_without_merge_errors(self):
        errs = [e for e in self._errors_as_array()
                if e['code'] != errors.MERGE_REQUIRED[0]]
        return errs

    def has_errors(self):
        return len(self._errors_as_array()) > 0

    def get_fields_with_error(self):
        data = {}
        datadict = self.datadict

        for e in self._errors_as_array():
            for field in e['fields']:
                data[field] = datadict[field]

        return data

    def has_fatal_error(self):
        if self.errors:
            for err in json.loads(self.errors):
                if err['fatal']:
                    return True

        return False

    def append_error(self, err, fields, data=None):
        code, msg, fatal = err

        if self.errors is None or self.errors == '':
            self.errors = '[]'

        # If you give append_error a single field
        # there is no need to get angry
        if isinstance(fields, basestring):
            fields = (fields,)  # make into tuple

        self.errors = json.dumps(
            json.loads(self.errors) + [
                {'code': code,
                 'fields': fields,
                 'data': data,
                 'fatal': fatal}])

        return self

    def safe_float(self, fld):
        try:
            return float(self.datadict[fld])
        except:
            self.append_error(errors.FLOAT_ERROR, fld)
            return False

    def safe_bool(self, fld):
        """ Returns a tuple of (success, bool value) """
        v = self.datadict.get(fld, '').lower()

        if v == '':
            return (True, None)
        if v == 'true' or v == 't' or v == 'yes':
            return (True, True)
        elif v == 'false' or v == 'f' or v == 'no':
            return (True, False)
        else:
            self.append_error(errors.BOOL_ERROR, fld)
            return (False, None)

    def safe_int(self, fld):
        try:
            return int(self.datadict[fld])
        except:
            self.append_error(errors.INT_ERROR, fld)
            return False

    def safe_pos_int(self, fld):
        i = self.safe_int(fld)

        if i is False:
            return False
        elif i < 0:
            self.append_error(errors.POS_INT_ERROR, fld)
            return False
        else:
            return i

    def safe_pos_float(self, fld):
        i = self.safe_float(fld)

        if i is False:
            return False
        elif i < 0:
            self.append_error(errors.POS_FLOAT_ERROR, fld)
            return False
        else:
            return i

    def convert_units(self, data, converts):
        for fld, factor in converts.iteritems():
            if fld in data and factor != 1.0:
                data[fld] = float(data[fld]) * factor

    def validate_numeric_fields(self):
        def cleanup(fields, fn):
            has_errors = False
            for f in fields:
                if f in self.datadict and self.datadict[f]:
                    maybe_num = fn(f)

                    if maybe_num is False:
                        has_errors = True
                    else:
                        self.cleaned[f] = maybe_num

            return has_errors

        pfloat_ok = cleanup(self.model_fields.POS_FLOAT_FIELDS,
                            self.safe_pos_float)

        float_ok = cleanup(self.model_fields.FLOAT_FIELDS,
                           self.safe_float)

        int_ok = cleanup(self.model_fields.POS_INT_FIELDS,
                         self.safe_pos_int)

        return pfloat_ok and float_ok and int_ok

    def validate_boolean_fields(self):
        has_errors = False
        for f in self.model_fields.BOOLEAN_FIELDS:
            if f in self.datadict:
                success, v = self.safe_bool(f)
                if success and v is not None:
                    self.cleaned[f] = v
                else:
                    has_errors = True

        return has_errors

    def validate_string_fields(self):
        has_errors = False
        for field in self.model_fields.STRING_FIELDS:

            value = self.datadict.get(field, None)
            if value:
                if len(value) > 255:
                    self.append_error(errors.STRING_TOO_LONG, field)
                    has_errors = True
                else:
                    self.cleaned[field] = value

        return has_errors

    def validate_date_fields(self):
        has_errors = False
        for field in self.model_fields.DATE_FIELDS:
            value = self.datadict.get(field, None)
            if value:
                try:
                    datep = datetime.strptime(value, '%Y-%m-%d')
                    self.cleaned[field] = datep
                except ValueError:
                    self.append_error(errors.INVALID_DATE, field)
                    has_errors = True

        return has_errors

    def validate_and_convert_datatypes(self):
        self.validate_numeric_fields()
        self.validate_boolean_fields()
        self.validate_string_fields()
        self.validate_date_fields()

    def validate_row(self):
        """
        Validate a row. Returns True if there were no fatal errors,
        False otherwise

        The method mutates self in two ways:
        - The 'errors' field on self will be appended to
          whenever an error is found
        - The 'cleaned' field on self will be set as fields
          get validated
        """
        raise Exception('Abstract Method')

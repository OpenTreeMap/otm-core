# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import csv
import json

from celery import task
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from importer.models.base import GenericImportEvent, GenericImportRow
from importer.models.species import SpeciesImportEvent, SpeciesImportRow
from importer.models.trees import TreeImportEvent, TreeImportRow
from importer import errors
from importer.util import lowerkeys

BLOCK_SIZE = 250


@transaction.atomic
def _create_rows_for_event(ie, csvfile):
    rows = []
    reader = csv.DictReader(csvfile)

    fieldnames = reader.fieldnames
    ie.field_order = json.dumps(fieldnames)
    ie.save()

    idx = 0
    for row in reader:
        # TODO: should we even create a row if
        # we're about to break out? It's not like
        # the file errors get attached to the row
        # anyway.
        rows.append(
            ie.create_row(
                data=json.dumps(lowerkeys(row)),
                import_event=ie, idx=idx))

        # perform file validation with first row
        if idx == 0:
            # Break out early if there was an error
            # with the basic file structure
            ie.validate_main_file()
            if ie.has_errors():
                break
        idx += 1
    else:
        ie.validate_main_file()

    return False if ie.has_errors() else rows


@task()
def run_import_event_validation(import_type, import_event_id, file_obj):
    ie = _get_import_event(import_type, import_event_id)

    try:
        rows = _create_rows_for_event(ie, file_obj)
    except Exception as e:
        ie.append_error(errors.GENERIC_ERROR, data=[str(e)])
        ie.status = GenericImportEvent.FAILED_FILE_VERIFICATION
        ie.save()
        rows = None

    if not rows:
        return

    filevalid = ie.validate_main_file()

    ie.status = GenericImportEvent.VERIFIYING
    ie.save()

    rows = ie.rows()
    if filevalid:
        for i in xrange(0, rows.count(), BLOCK_SIZE):
            _validate_rows.delay(import_type, import_event_id, i)


@task()
def _validate_rows(import_type, import_event_id, i):
    ie = _get_import_event(import_type, import_event_id)
    for row in ie.rows()[i:(i+BLOCK_SIZE)]:
        row.validate_row()

    if _get_waiting_row_count(ie) == 0:
        ie.status = GenericImportEvent.FINISHED_VERIFICATION
        ie.save()


@task()
def commit_import_event(import_type, import_event_id):
    ie = _get_import_event(import_type, import_event_id)
    filevalid = ie.validate_main_file()

    if filevalid:
        rows = ie.rows()
        for i in xrange(0, rows.count(), BLOCK_SIZE):
            _commit_rows.delay(import_type, import_event_id, i)


@task()
@transaction.atomic
def _commit_rows(import_type, import_event_id, i):
    ie = _get_import_event(import_type, import_event_id)

    for row in ie.rows()[i:(i + BLOCK_SIZE)]:
        row.commit_row()

    if _get_waiting_row_count(ie) == 0:
        ie.status = GenericImportEvent.FINISHED_CREATING
        ie.save()


def _get_import_event(import_type, import_event_id):
    Model = get_import_event_model(import_type)
    try:
        return Model.objects.get(pk=import_event_id)
    except ObjectDoesNotExist:
        raise Exception('Import event not found "%s" %s'
                        % (import_type, import_event_id))


def get_import_event_model(import_type):
    if import_type == SpeciesImportEvent.import_type:
        Model = SpeciesImportEvent
    elif import_type == TreeImportEvent.import_type:
        Model = TreeImportEvent
    else:
        raise Exception('Invalid import type "%s"' % import_type)
    return Model


def get_import_row_model(import_type):
    if import_type == SpeciesImportEvent.import_type:
        Model = SpeciesImportRow
    elif import_type == TreeImportEvent.import_type:
        Model = TreeImportRow
    else:
        raise Exception('Invalid import type "%s"' % import_type)
    return Model


def _get_waiting_row_count(ie):
    return ie.rows()\
             .filter(status=GenericImportRow.WAITING)\
             .count()

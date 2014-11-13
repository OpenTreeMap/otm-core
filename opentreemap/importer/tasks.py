# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from celery import task
from django.core.exceptions import ObjectDoesNotExist

from importer.models import GenericImportEvent, GenericImportRow
from importer.species import SpeciesImportEvent
from importer.trees import TreeImportEvent

BLOCK_SIZE = 250


@task()
def run_import_event_validation(import_type, import_event_id):
    ie = _get_import_event(import_type, import_event_id)
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

    rows = ie.rows()

    if filevalid:
        for i in xrange(0, rows.count(), BLOCK_SIZE):
            _commit_rows.delay(import_type, import_event_id, i)


@task()
def _commit_rows(import_type, import_event_id, i):
    ie = _get_import_event(import_type, import_event_id)
    missing_merges = 0

    for row in ie.rows()[i:(i + BLOCK_SIZE)]:
        needs_merge = hasattr(row, 'merged') and not row.merged
        if row.status != GenericImportRow.SUCCESS and not needs_merge:
            row.commit_row()

        if needs_merge:
            missing_merges += 1

    if _get_waiting_row_count(ie) <= missing_merges:
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


def _get_waiting_row_count(ie):
    return ie.rows()\
             .filter(status=GenericImportRow.WAITING)\
             .count()

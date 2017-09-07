# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json

from celery import shared_task, chord
from celery.result import GroupResult
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from django.db import transaction

from importer.models.base import GenericImportEvent, GenericImportRow
from importer.models.species import SpeciesImportEvent, SpeciesImportRow
from importer.models.trees import TreeImportEvent, TreeImportRow
from importer import errors
from importer.util import (clean_row_data, clean_field_name,
                           utf8_file_to_csv_dictreader)


def _create_rows_for_event(ie, csv_file):
    # Don't use a transaction for this possibly long-running operation
    # so we can show progress. Caller does manual cleanup if necessary.
    reader = utf8_file_to_csv_dictreader(csv_file)

    field_names = [f.strip().decode('utf-8') for f in reader.fieldnames
                   if f.strip().lower() not in ie.ignored_fields()]
    ie.field_order = json.dumps(field_names)
    ie.save()

    field_names = [clean_field_name(f) for f in field_names]
    file_valid = ie.validate_field_names(field_names)

    if file_valid:
        _create_rows(ie, reader)

        if ie.row_count == 0:
            file_valid = False
            ie.append_error(errors.EMPTY_FILE)

    if file_valid:
        return True
    else:
        ie.status = ie.FAILED_FILE_VERIFICATION
        ie.mark_finished_and_save()
        return False


def _create_rows(ie, reader):
    RowModel = get_import_row_model(ie.import_type)
    rows = []
    idx = 0

    for row in reader:
        data = clean_row_data(row)
        if len(filter(None, data.values())) > 0:  # skip blank rows
            data = json.dumps(data)
            rows.append(RowModel(data=data, import_event=ie, idx=idx))

            idx += 1
            if ((int(idx / settings.IMPORT_BATCH_SIZE) *
                 settings.IMPORT_BATCH_SIZE == idx)):
                RowModel.objects.bulk_create(rows)
                rows = []

    if rows:
        RowModel.objects.bulk_create(rows)  # create final partial block


@shared_task()
def run_import_event_validation(import_type, import_event_id, file_obj):
    ie = _get_import_event(import_type, import_event_id)

    try:
        ie.status = GenericImportEvent.LOADING
        ie.update_progress_timestamp_and_save()
        success = _create_rows_for_event(ie, file_obj)
    except Exception as e:
        ie.append_error(errors.GENERIC_ERROR, data=[str(e)])
        ie.status = GenericImportEvent.FAILED_FILE_VERIFICATION
        ie.mark_finished_and_save()
        success = False

    if not success:
        try:
            ie.row_set().delete()
        except Exception:
            pass
        return

    ie.status = GenericImportEvent.PREPARING_VERIFICATION
    ie.update_progress_timestamp_and_save()

    try:
        validation_tasks = []
        for i in xrange(0, ie.row_count, settings.IMPORT_BATCH_SIZE):
            validation_tasks.append(_validate_rows.s(import_type, ie.id, i))

        final_task = _finalize_validation.si(import_type, import_event_id)

        async_result = chord(validation_tasks, final_task).delay()
        async_result_parent = async_result.parent
        if async_result_parent:  # Has value None when run in unit tests
            # Celery 4 converts a chord with only one task in the head into
            # a simple chain, which does not have a savable parent GroupResult
            if isinstance(async_result_parent, GroupResult):
                async_result_parent.save()
            ie.task_id = async_result_parent.id

        _assure_status_is_at_least_verifying(ie)

    except Exception as e:
        ie.status = GenericImportEvent.VERIFICATION_ERROR
        ie.mark_finished_and_save()
        try:
            ie.append_error(errors.GENERIC_ERROR, data=[str(e)])
            ie.save()
            # I don't think this ever worked in the past.
            # TODO: delete?
            ie.rows().delete()
        except Exception:
            # This has shown to swallow real exceptions in development.
            # TODO: At the very least, we should add logging.
            pass
        return


@transaction.atomic
def _assure_status_is_at_least_verifying(ie):
    # Protect against race condition between task completion and main task
    ie.refresh_from_db()
    if not ie.is_past_verifying_stage():
        ie.status = GenericImportEvent.VERIFIYING
        ie.update_progress_timestamp_and_save()


@shared_task()
def _validate_rows(import_type, import_event_id, start_row_id):
    ie = _get_import_event(import_type, import_event_id)
    rows = ie.rows()[start_row_id:(start_row_id+settings.IMPORT_BATCH_SIZE)]
    for row in rows:
        row.validate_row()
    ie.update_progress_timestamp_and_save()


@shared_task()
def _finalize_validation(import_type, import_event_id):
    ie = _get_import_event(import_type, import_event_id)

    # There shouldn't be any rows left to verify, but it doesn't hurt to check
    if _get_waiting_row_count(ie) == 0:
        ie.status = GenericImportEvent.FINISHED_VERIFICATION
    else:
        # TODO: if we're going to check, we should probably raise
        pass

    ie.mark_finished_and_save()


@shared_task()
def commit_import_event(import_type, import_event_id):
    ie = _get_import_event(import_type, import_event_id)

    commit_tasks = [
        _commit_rows.s(import_type, import_event_id, i)
        for i in xrange(0, ie.row_count, settings.IMPORT_BATCH_SIZE)]

    finalize_task = _finalize_commit.si(import_type, import_event_id)

    async_result = chord(commit_tasks, finalize_task).delay()
    # Protect against a race condition where finalize_task's ie
    # may have already been updated to FINISHED_CREATING and saved to the db,
    # rendering this instance of the ie model obsolete.
    ie.refresh_from_db()
    if async_result:
        ie.task_id = async_result.id
        ie.save()


@shared_task(rate_limit=settings.IMPORT_COMMIT_RATE_LIMIT)
def _commit_rows(import_type, import_event_id, i):
    ie = _get_import_event(import_type, import_event_id)

    for row in ie.rows()[i:(i + settings.IMPORT_BATCH_SIZE)]:
        row.commit_row()
    ie.update_progress_timestamp_and_save()


@shared_task()
def _finalize_commit(import_type, import_event_id):
    ie = _get_import_event(import_type, import_event_id)

    ie.status = GenericImportEvent.FINISHED_CREATING
    ie.mark_finished_and_save()

    # A species import could change a species' i-Tree region,
    # affecting eco
    rev_updates = ['eco_rev', 'universal_rev']
    if import_type == TreeImportEvent.import_type:
        rev_updates.append('geo_rev')

    ie.instance.update_revs(*rev_updates)


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


@shared_task
def get_import_export(import_type, import_event_id):
    ie = _get_import_event(import_type, import_event_id)

    return [clean_row_data(json.loads(row.data)) for row in ie.rows()]

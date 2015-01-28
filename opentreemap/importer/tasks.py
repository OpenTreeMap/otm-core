# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import csv
import json

from celery import task, chord
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from treemap.models import Species

from importer.models.base import GenericImportEvent, GenericImportRow
from importer.models.species import SpeciesImportEvent, SpeciesImportRow
from importer.models.trees import TreeImportEvent, TreeImportRow
from importer import errors, fields
from importer.util import clean_row_data, clean_field_name

BLOCK_SIZE = 250


def _create_rows_for_event(ie, csv_file):
    # Don't use a transaction for this possibly long-running operation
    # so we can show progress. Caller does manual cleanup if necessary.
    reader = csv.DictReader(csv_file)

    field_names = reader.fieldnames
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
        ie.save()
        return False


def _create_rows(ie, reader):
    RowModel = get_import_row_model(ie.import_type)
    rows = []
    idx = 0

    for row in reader:
        data = json.dumps(clean_row_data(row))
        rows.append(RowModel(data=data, import_event=ie, idx=idx))

        idx += 1
        if int(idx / BLOCK_SIZE) * BLOCK_SIZE == idx:
            RowModel.objects.bulk_create(rows)
            rows = []

    if rows:
        RowModel.objects.bulk_create(rows)  # create final partial block


@task()
def run_import_event_validation(import_type, import_event_id, file_obj):
    ie = _get_import_event(import_type, import_event_id)

    try:
        ie.status = GenericImportEvent.LOADING
        ie.save()
        success = _create_rows_for_event(ie, file_obj)
    except Exception as e:
        ie.append_error(errors.GENERIC_ERROR, data=[str(e)])
        ie.status = GenericImportEvent.FAILED_FILE_VERIFICATION
        ie.save()
        success = False

    if not success:
        try:
            ie.row_set().delete()
        except Exception:
            pass
        return

    ie.status = GenericImportEvent.VERIFIYING
    ie.save()

    row_set = ie.rows()
    validation_tasks = (_validate_rows.subtask(row_set[i:(i+BLOCK_SIZE)])
                        for i in xrange(0, ie.row_count, BLOCK_SIZE))

    final_task = _finalize_validation.si(import_type, import_event_id)
    res = chord(validation_tasks, final_task).delay()

    ie.task_id = res.id
    ie.save()


@task()
def _validate_rows(*rows):
    for row in rows:
        row.validate_row()


@task()
def _finalize_validation(import_type, import_event_id):
    ie = _get_import_event(import_type, import_event_id)

    ie.task_id = ''
    # There shouldn't be any rows left to verify, but it doesn't hurt to check
    if _get_waiting_row_count(ie) == 0:
        ie.status = GenericImportEvent.FINISHED_VERIFICATION

    ie.save()


@task()
def commit_import_event(import_type, import_event_id):
    ie = _get_import_event(import_type, import_event_id)
    for i in xrange(0, ie.row_count, BLOCK_SIZE):
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


def _species_export_builder(model):
    model_dict = model.as_dict()
    obj = {}

    for k, v in SpeciesImportRow.SPECIES_MAP:
        if v in fields.species.ALL:
            if k in model_dict:
                val = model_dict[k]
                if not val is None:
                    obj[v] = val
    return obj


@task
def get_all_species_export(instance_id):
    return [_species_export_builder(species) for species
            in Species.objects.filter(instance_id=instance_id)]


@task
def get_import_export(import_type, import_event_id):
    ie = _get_import_event(import_type, import_event_id)

    return [clean_row_data(json.loads(row.data)) for row in ie.rows()]

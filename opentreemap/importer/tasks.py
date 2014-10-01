from celery import task

from importer.models import TreeImportRow, GenericImportEvent, \
    GenericImportRow

BLOCK_SIZE = 250

def get_waiting_row_count(ie):
    return ie.rows()\
             .filter(status=GenericImportRow.WAITING)\
             .count()


@task()
def validate_rows(ie, i):
    for row in ie.rows()[i:(i+BLOCK_SIZE)]:
        row.validate_row()

    if get_waiting_row_count(ie) == 0:
        ie.status = GenericImportEvent.FINISHED_VERIFICATION
        ie.save()

@task()
def run_import_event_validation(ie):
    filevalid = ie.validate_main_file()

    ie.status = GenericImportEvent.VERIFIYING
    ie.save()

    rows = ie.rows()
    if filevalid:
        for i in xrange(0,rows.count(), BLOCK_SIZE):
            validate_rows.delay(ie, i)

@task()
def commit_rows(ie, i):
    #TODO: Refactor out [Tree]ImportRow.SUCCESS
    # this works right now because they are the same
    # value (0) but that's not really great
    missing_merges = 0

    for row in ie.rows()[i:(i + BLOCK_SIZE)]:
        needs_merge = hasattr(row, 'merged') and not row.merged
        if row.status != TreeImportRow.SUCCESS and not needs_merge:
            row.commit_row()

        if needs_merge:
            missing_merges += 1

    if get_waiting_row_count(ie) <= missing_merges:
        ie.status = GenericImportEvent.FINISHED_CREATING
        ie.save()

@task()
def commit_import_event(ie):
    filevalid = ie.validate_main_file()

    rows = ie.rows()
    success = []
    failed = []

    #TODO: When using OTM ID field, don't include
    #      that tree in proximity check (duh)
    if filevalid:
        for i in xrange(0,rows.count(), BLOCK_SIZE):
            commit_rows.delay(ie, i)

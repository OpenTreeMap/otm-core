# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import math

from django.http import HttpResponse, Http404
from django.utils.translation import ugettext as _
from django.db import transaction

from treemap.audit import (Audit, approve_or_reject_existing_edit,
                           approve_or_reject_audits_and_apply)
from treemap.models import MapFeaturePhoto


_PHOTO_PAGE_SIZE = 12


def _photo_audits(instance):
    unverified_actions = {Audit.Type.Insert,
                          Audit.Type.Delete,
                          Audit.Type.Update}

    # Only return audits for photos that haven't been deleted
    photo_ids = MapFeaturePhoto.objects.filter(instance=instance)\
                                       .values_list('id', flat=True)

    audits = Audit.objects.filter(instance=instance,
                                  model__in=['TreePhoto', 'MapFeaturePhoto'],
                                  field='image',
                                  ref__isnull=True,
                                  action__in=unverified_actions,
                                  model_id__in=photo_ids)\
                          .order_by('-created')

    return audits


def _process_page_number(request, total):
    page = int(request.REQUEST.get('n', '1'))

    # For some reason, despite importing division from the future
    # total / PHOTO_PAGE_SIZE does integer division
    total_pages = int(math.ceil(float(total) / _PHOTO_PAGE_SIZE))

    startidx = (page-1) * _PHOTO_PAGE_SIZE
    endidx = startidx + _PHOTO_PAGE_SIZE

    return (page, total_pages, startidx, endidx)


def next_photo(request, instance):
    audits = _photo_audits(instance)

    total = audits.count()
    page, total_pages, startidx, endidx = _process_page_number(request, total)

    # We're done!
    if total == 0 or total < _PHOTO_PAGE_SIZE:
        photo = None
    else:
        try:
            photo_id = audits[endidx].model_id
        except IndexError:
            # We may have finished an entire page
            # in that case, simply return the last image
            photo_id = audits[total-1].model_id

        photo = (MapFeaturePhoto.objects
                 .select_related('treephoto')
                 .get(pk=photo_id))

    return {
        'photo': photo,
        'total_pages': total_pages
    }


def photo_review(request, instance):
    audits = _photo_audits(instance)

    total = audits.count()
    page, total_pages, startidx, endidx = _process_page_number(request, total)

    audits = audits[startidx:endidx]

    prev_page = page - 1
    if prev_page <= 0:
        prev_page = None

    next_page = page + 1
    if next_page > total_pages:
        next_page = None

    pages = range(1, total_pages+1)
    if len(pages) > 10:
        pages = pages[0:8] + [pages[-1]]

    return {
        'photos': [(MapFeaturePhoto.objects
                    .select_related('treephoto')
                    .get(pk=audit.model_id))
                   for audit in audits],
        'pages': pages,
        'total_pages': total_pages,
        'cur_page': page,
        'next_page': next_page,
        'prev_page': prev_page
    }


@transaction.atomic
def approve_or_reject_photo(
        request, instance, feature_id, photo_id, action):

    approved = action == 'approve'

    if approved:
        msg = _('Approved')
    else:
        msg = _('Rejected')

    resp = HttpResponse(msg)

    try:
        photo = (MapFeaturePhoto.objects
                 .select_related('treephoto')
                 .get(pk=photo_id))
        try:
            photo = photo.treephoto
        except MapFeaturePhoto.DoesNotExist:
            pass  # There is no tree photo, so use the superclass
    except MapFeaturePhoto.DoesNotExist:
        # This may be a pending tree. Let's see if there
        # are pending audits
        pending_audits = Audit.objects\
            .filter(instance=instance)\
            .filter(model__in=['TreePhoto', 'MapFeaturePhoto'])\
            .filter(model_id=photo_id)\
            .filter(requires_auth=True)

        if len(pending_audits) > 0:
            # Process as pending and quit
            approve_or_reject_audits_and_apply(
                pending_audits, request.user, approved)

            return resp
        else:
            # Error - no pending or regular
            raise Http404('Photo Not Found')

    # Handle the id audit first
    all_audits = []
    for audit in photo.audits():
        if audit.field == 'id':
            all_audits = [audit] + all_audits
        else:
            all_audits.append(audit)

    for audit in all_audits:
        approve_or_reject_existing_edit(
            audit, request.user, approved)

    return resp

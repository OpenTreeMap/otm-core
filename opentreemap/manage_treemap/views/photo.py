# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.core.paginator import Paginator, EmptyPage
from django.db import transaction
from django.http import Http404
from django.utils.translation import ugettext as _

from opentreemap.util import get_ids_from_request

from treemap.audit import (Audit, approve_or_reject_existing_edit,
                           approve_or_reject_audits_and_apply)
from treemap.lib.page_of_items import UrlParams, make_filter_context
from treemap.models import MapFeaturePhoto


_PHOTO_PAGE_SIZE = 5


def get_photos(instance, sort_order='-created_at', is_archived=False):
    unverified_actions = {Audit.Type.Insert,
                          Audit.Type.Delete,
                          Audit.Type.Update}

    audit_model_ids = Audit.objects \
        .filter(
            instance=instance,
            model__in=['TreePhoto', 'MapFeaturePhoto'],
            field='image',
            ref__isnull=not is_archived,
            action__in=unverified_actions) \
        .values_list('model_id', flat=True)

    photos = MapFeaturePhoto.objects \
        .filter(
            instance=instance,
            id__in=audit_model_ids,
            map_feature__feature_type__in=instance.map_feature_types) \
        .order_by(sort_order)

    return photos


def photo_review(request, instance):
    page_number = int(request.GET.get('page', '1'))
    sort_order = request.GET.get('sort', '-created_at')
    is_archived = request.GET.get('archived', 'False') == 'True'

    photos = get_photos(instance, sort_order, is_archived)
    paginator = Paginator(photos, _PHOTO_PAGE_SIZE)

    try:
        paged_photos = paginator.page(page_number)
    except EmptyPage:
        # If the page number is out of bounds, return the last page
        paged_photos = paginator.page(paginator.num_pages)

    urlizer = UrlParams('photo_review_partial', instance.url_name,
                        page=page_number, sort=sort_order,
                        archived=is_archived)

    filter_value = dict(archived=is_archived)

    filter_context = make_filter_context(urlizer, filter_value, [
        (_('Active'), _('active'), dict(archived=False)),
        (_('Archived'), _('archived'), dict(archived=True)),
    ])
    filter_context['container_attr'] = 'data-photo-filter'

    return {
        'photos': paged_photos,
        'sort_order': sort_order,
        'is_archived': is_archived,
        'archived_filter': filter_context,
        'url_for_pagination': urlizer.url('sort', 'archived'),
        'url_for_sort': urlizer.url('archived'),
        'full_params': urlizer.params('page', 'sort', 'archived')
    }


@transaction.atomic
def approve_or_reject_photos(request, instance, action):
    approved = action == 'approve'

    photo_ids = get_ids_from_request(request)

    for photo_id in photo_ids:
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

                return photo_review(request, instance)
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

    return photo_review(request, instance)

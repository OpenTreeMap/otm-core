# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division


from djqscsv import render_to_csv_response

from django.core.paginator import Paginator, EmptyPage

from opentreemap.util import decorate as do

from treemap.decorators import admin_instance_request, require_http_method

from otm_comments.models import EnhancedThreadedComment


def _comments(request, instance):
    is_archived = request.GET.get('archived', None)
    is_removed = request.GET.get('removed', None)
    sort = request.GET.get('sort', '-submit_date')

    comments = EnhancedThreadedComment.objects \
        .filter(instance=instance) \
        .prefetch_related('content_object') \
        .order_by(sort)

    if is_archived is not None:
        is_archived = is_archived == 'True'
        comments = comments.filter(is_archived=is_archived)

    if is_removed is not None:
        is_removed = is_removed == 'True'
        comments = comments.filter(is_removed=is_removed)

    return comments


def comments_review(request, instance):
    page_number = int(request.GET.get('page', '1'))
    page_size = int(request.GET.get('size', '5'))

    comments = _comments(request, instance)
    paginator = Paginator(comments, page_size)

    try:
        paged_comments = paginator.page(page_number)
    except EmptyPage:
        # If the page number is out of bounds, return the last page
        paged_comments = paginator.page(paginator.num_pages)

    return {
        'comments': paged_comments
    }


def comments_csv(request, instance):
    comments = _comments(request, instance)
    qs = comments.values(
        'id',
        'user__username',
        'comment',
        'is_removed',
        'is_archived',
        'submit_date'
    )
    return render_to_csv_response(qs)


comments_csv_endpoint = do(
    require_http_method("GET"),
    admin_instance_request,
    comments_csv)

# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division


from django.core.paginator import Paginator, EmptyPage

from otm_comments.models import EnhancedThreadedComment


def comments_review(request, instance):
    is_archived = request.GET.get('archived', None)
    is_removed = request.GET.get('removed', None)
    sort = request.GET.get('sort', '-submit_date')
    page_number = int(request.GET.get('page', '1'))
    page_size = int(request.GET.get('size', '5'))

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

    paginator = Paginator(comments, page_size)

    try:
        paged_comments = paginator.page(page_number)
    except EmptyPage:
        # If the page number is out of bounds, return the last page
        paged_comments = paginator.page(paginator.num_pages)

    return {
        'comments': paged_comments
    }

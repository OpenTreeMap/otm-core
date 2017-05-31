# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from functools import partial

from django.core.paginator import Paginator, EmptyPage
from django.db import transaction
from django.utils.translation import ugettext as _

from django_tinsel.utils import decorate as do
from django_tinsel.decorators import json_api_call, render_template

from opentreemap.util import get_ids_from_request

from treemap.decorators import (instance_request, admin_instance_request,
                                require_http_method)
from treemap.lib.page_of_items import UrlParams, make_filter_context

from exporter.decorators import queryset_as_exported_csv

from otm_comments.models import (EnhancedThreadedComment,
                                 EnhancedThreadedCommentFlag)


def _comments_params(params):
    # The default view shows all unarchived comments
    is_archived = params.get('archived', 'False')
    is_removed = params.get('removed', 'None')
    sort = params.get('sort', '-submit_date')

    is_archived = None if is_archived == 'None' else (is_archived == 'True')
    is_removed = None if is_removed == 'None' else (is_removed == 'True')

    return (is_archived, is_removed, sort)


def get_comments(params, instance):
    (is_archived, is_removed, sort) = _comments_params(params)

    # Note: we tried .prefetch_related('content_object')
    # but it gives comment.content_object = None  (Django 1.6)

    types = {t.lower() for t in instance.map_feature_types}
    comments = EnhancedThreadedComment.objects \
        .filter(content_type__model__in=types) \
        .filter(instance=instance) \
        .extra(select={
            'visible_flag_count': 'SELECT COUNT(*) ' +
            'FROM otm_comments_enhancedthreadedcommentflag ' +
            'WHERE otm_comments_enhancedthreadedcommentflag.comment_id = ' +
            'otm_comments_enhancedthreadedcomment.threadedcomment_ptr_id ' +
            'AND not hidden'})\
        .extra(order_by=[sort])

    if is_archived is not None:
        comments = comments.filter(is_archived=is_archived)

    if is_removed is not None:
        comments = comments.filter(is_removed=is_removed)

    return comments


def comment_moderation(request, instance):
    (is_archived, is_removed, sort) = _comments_params(request.GET)
    page_number = int(request.GET.get('page', '1'))
    page_size = int(request.GET.get('size', '5'))

    comments = get_comments(request.GET, instance)
    paginator = Paginator(comments, page_size)

    try:
        paged_comments = paginator.page(page_number)
    except EmptyPage:
        # If the page number is out of bounds, return the last page
        paged_comments = paginator.page(paginator.num_pages)

    urlizer = UrlParams('comment_moderation', instance.url_name,
                        archived=is_archived, sort=sort, removed=is_removed,
                        page=paged_comments.number)

    comments_url_for_pagination = urlizer.url('archived', 'removed', 'sort')
    comments_url_for_sort = urlizer.url('archived', 'removed')

    full_params = urlizer.params('archived', 'removed', 'sort', 'page')

    checked_comments = get_ids_from_request(request)
    if len(checked_comments) == 1:
        # Don't check the box for non-batch requests
        checked_comments = []

    filter_value = dict(archived=is_archived, removed=is_removed)

    filter_context = make_filter_context(urlizer, filter_value, [
        (_('Active'), _('active'), dict(archived=False, removed=None)),
        (_('Hidden'), _('hidden'), dict(archived=None, removed=True)),
        (_('Archived'), _('archived'), dict(archived=True, removed=None)),
    ])
    filter_context['container_attr'] = 'data-comments-filter'

    return {
        'comments': paged_comments,
        'comments_filter': filter_context,
        'comments_url_for_pagination': comments_url_for_pagination,
        'comments_url_for_sort': comments_url_for_sort,
        'comments_params': full_params,
        'comments_sort': sort,
        'comment_ids': checked_comments
    }


def comments_csv(request, instance):
    comments = get_comments(request.GET, instance)
    return comments.values(
        'id',
        'user__username',
        'comment',
        'is_removed',
        'is_archived',
        'visible_flag_count',
        'submit_date'
    )


@transaction.atomic
def flag(request, instance, comment_id):
    comment = EnhancedThreadedComment.objects.get(pk=comment_id,
                                                  instance=instance)
    user_already_has_visible_flag = len(
        comment.enhancedthreadedcommentflag_set.filter(
            user=request.user, hidden=False)) > 0
    if not user_already_has_visible_flag:
        comment.enhancedthreadedcommentflag_set.create(user=request.user)
        # Much like an archived email thread appears in your inbox when
        # there is a new reply, flagging a comment removes it from the archive
        comment.is_archived = False
        comment.save()
    return {'comment': comment}


@transaction.atomic
def unflag(request, instance, comment_id):
    comment = EnhancedThreadedComment.objects.get(pk=comment_id,
                                                  instance=instance)
    flags = comment.enhancedthreadedcommentflag_set.filter(user=request.user)
    flags.update(hidden=True)
    return {'comment': comment}


@transaction.atomic
def hide_flags(request, instance):
    comment_ids = get_ids_from_request(request)
    EnhancedThreadedCommentFlag.objects.filter(comment__id__in=comment_ids,
                                               comment__instance=instance)\
        .update(hidden=True)
    return comment_moderation(request, instance)


def _set_prop_on_comments(request, instance, prop_name, prop_value):
    comment_ids = get_ids_from_request(request)
    comments = EnhancedThreadedComment.objects.filter(
        pk__in=comment_ids, instance=instance)

    for comment in comments:
        setattr(comment, prop_name, prop_value)
        comment.save()
    return comment_moderation(request, instance)


@transaction.atomic
def archive(request, instance):
    return _set_prop_on_comments(request, instance, 'is_archived', True)


@transaction.atomic
def unarchive(request, instance):
    return _set_prop_on_comments(request, instance, 'is_archived', False)


@transaction.atomic
def hide(request, instance):
    return _set_prop_on_comments(request, instance, 'is_removed', True)


@transaction.atomic
def show(request, instance):
    return _set_prop_on_comments(request, instance, 'is_removed', False)


_admin_post_do = partial(do, require_http_method("POST"),
                         admin_instance_request,
                         render_template(
                             "otm_comments/partials/moderation.html"))

_render_flagging_view = partial(
    do,
    require_http_method("POST"),
    instance_request,
    render_template("otm_comments/partials/flagging.html"))

flag_endpoint = _render_flagging_view(flag)
unflag_endpoint = _render_flagging_view(unflag)
hide_flags_endpoint = _admin_post_do(hide_flags)
archive_endpoint = _admin_post_do(archive)
unarchive_endpoint = _admin_post_do(unarchive)
hide_endpoint = _admin_post_do(hide)
show_endpoint = _admin_post_do(show)

comments_csv_endpoint = do(
    require_http_method("GET"),
    admin_instance_request,
    json_api_call,
    queryset_as_exported_csv,
    comments_csv)

comment_moderation_partial_endpoint = do(
    require_http_method("GET"),
    admin_instance_request,
    render_template('otm_comments/partials/moderation.html'),
    comment_moderation)

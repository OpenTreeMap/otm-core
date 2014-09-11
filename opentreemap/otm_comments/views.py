# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from functools import partial

from djqscsv import render_to_csv_response

from django.core.paginator import Paginator, EmptyPage
from django.db import transaction

from opentreemap.util import decorate as do

from treemap.decorators import (instance_request, admin_instance_request,
                                require_http_method, json_api_call,
                                render_template)

from otm_comments.models import (EnhancedThreadedComment,
                                 EnhancedThreadedCommentFlag)


def _comments(request, instance):
    is_archived = request.GET.get('archived', None)
    is_removed = request.GET.get('removed', None)
    sort = request.GET.get('sort', '-submit_date')

    # Note: we tried .prefetch_related('content_object')
    # but it gives comment.content_object = None  (Django 1.6)
    comments = EnhancedThreadedComment.objects \
        .filter(instance=instance) \
        .extra(select={
            'visible_flag_count': 'SELECT COUNT(*) ' +
            'FROM otm_comments_enhancedthreadedcommentflag ' +
            'WHERE otm_comments_enhancedthreadedcommentflag.comment_id = ' +
            'otm_comments_enhancedthreadedcomment.threadedcomment_ptr_id ' +
            'AND not hidden'})\
        .order_by(sort)

    if is_archived is not None:
        is_archived = is_archived == 'True'
        comments = comments.filter(is_archived=is_archived)

    if is_removed is not None:
        is_removed = is_removed == 'True'
        comments = comments.filter(is_removed=is_removed)

    return comments


def comment_moderation(request, instance):
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
        'visible_flag_count',
        'submit_date'
    )
    return render_to_csv_response(qs)


def _create_success_object_response():
    return {'success': True}


def _get_comment_ids(request):
    comment_ids_string = request.GET.get('comment-ids', None)
    if comment_ids_string:
        return [int(id) for id in comment_ids_string.split(',')]
    else:
        return []


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
    return _create_success_object_response()


@transaction.atomic
def unflag(request, instance, comment_id):
    EnhancedThreadedCommentFlag.objects.filter(
        comment__id=comment_id, comment__instance=instance,
        user=request.user).update(hidden=True)
    return _create_success_object_response()


@transaction.atomic
def hide_flags(request, instance):
    comment_ids = _get_comment_ids(request)
    EnhancedThreadedCommentFlag.objects.filter(comment__id__in=comment_ids,
                                               comment__instance=instance)\
        .update(hidden=True)
    return {'comments': EnhancedThreadedComment.objects.filter(
        pk__in=comment_ids, instance=instance)}


def _set_prop_on_comments(instance, comment_ids, prop_name, prop_value):
    comments = EnhancedThreadedComment.objects.filter(
        pk__in=comment_ids, instance=instance)

    for comment in comments:
        setattr(comment, prop_name, prop_value)
        comment.save()
    return {'comments': comments}


@transaction.atomic
def archive(request, instance):
    return _set_prop_on_comments(instance,
                                 _get_comment_ids(request),
                                 'is_archived', True)


@transaction.atomic
def unarchive(request, instance):
    return _set_prop_on_comments(instance,
                                 _get_comment_ids(request),
                                 'is_archived', False)


@transaction.atomic
def hide(request, instance):
    return _set_prop_on_comments(instance,
                                 _get_comment_ids(request),
                                 'is_removed', True)


@transaction.atomic
def show(request, instance):
    return _set_prop_on_comments(instance,
                                 _get_comment_ids(request),
                                 'is_removed', False)


_admin_post_do = partial(do, require_http_method("POST"),
                         admin_instance_request,
                         render_template(
                             "otm_comments/partials/moderation_rows.html"))

_post_returns_json_do = partial(do, require_http_method("POST"),
                                instance_request, json_api_call)

flag_endpoint = _post_returns_json_do(flag)
unflag_endpoint = _post_returns_json_do(unflag)
hide_flags_endpoint = _admin_post_do(hide_flags)
archive_endpoint = _admin_post_do(archive)
unarchive_endpoint = _admin_post_do(unarchive)
hide_endpoint = _admin_post_do(hide)
show_endpoint = _admin_post_do(show)

comments_csv_endpoint = do(
    require_http_method("GET"),
    admin_instance_request,
    comments_csv)

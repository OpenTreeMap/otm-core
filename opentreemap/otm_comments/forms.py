# -*- coding: utf-8 -*-


from threadedcomments.forms import ThreadedCommentForm

from otm_comments.models import EnhancedThreadedComment


class EnhancedThreadedCommentForm(ThreadedCommentForm):
    def get_comment_model(self, *args, **kwargs):
        return EnhancedThreadedComment

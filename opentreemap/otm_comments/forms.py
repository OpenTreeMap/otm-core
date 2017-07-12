# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from threadedcomments.forms import ThreadedCommentForm

from otm_comments.models import EnhancedThreadedComment


class EnhancedThreadedCommentForm(ThreadedCommentForm):
    def get_comment_model(self, *args, **kwargs):
        return EnhancedThreadedComment

# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division


from otm_comments.models import EnhancedThreadedComment
from threadedcomments.forms import ThreadedCommentForm


class EnhancedThreadedCommentForm(ThreadedCommentForm):
    def get_comment_model(self, *args, **kwargs):
        return EnhancedThreadedComment


# The contrib.comments app will load whichever app is specified in the settings
# by COMMENT_APP.  The two methods below will make it use our subclassed Model
def get_model():
    return EnhancedThreadedComment


def get_form():
    return EnhancedThreadedCommentForm

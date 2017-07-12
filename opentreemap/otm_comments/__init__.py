# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division


# The contrib.comments app will load whichever app is specified in the settings
# by COMMENT_APP.  The two methods below will make it use our subclassed Model
def get_model():
    # Delayed import, Apps won't be loaded yet when this module is
    from otm_comments.models import EnhancedThreadedComment
    return EnhancedThreadedComment


def get_form():
    # Delayed import, Apps won't be loaded yet when this module is
    from otm_comments.forms import EnhancedThreadedCommentForm
    return EnhancedThreadedCommentForm

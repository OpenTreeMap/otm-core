# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division


from threadedcomments.models import ThreadedComment

from django.contrib.gis.db import models

from treemap.instance import Instance


class EnhancedThreadedComment(ThreadedComment):
    """
    This class wraps the ThreadedComment model with moderation specific fields
    """

    # If the comment should be hidden in the default filter view for moderation
    is_archived = models.BooleanField(default=False)

    # We could retrieve this through the GenericForeignKey on ThreadedComment,
    # but it makes things simpler to record instance here.
    instance = models.ForeignKey(Instance)

    def save(self, *args, **kwargs):
        if hasattr(self.content_object, 'instance'):
            self.instance = self.content_object.instance

        super(EnhancedThreadedComment, self).save(*args, **kwargs)

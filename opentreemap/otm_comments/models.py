# -*- coding: utf-8 -*-


from threadedcomments.models import ThreadedComment

from django.conf import settings
from django.contrib.gis.db import models

from treemap.audit import Auditable


class EnhancedThreadedComment(ThreadedComment):
    """
    This class wraps the ThreadedComment model with moderation specific fields
    """

    # If the comment should be hidden in the default filter view for moderation
    is_archived = models.BooleanField(default=False)

    # We could retrieve this through the GenericForeignKey on ThreadedComment,
    # but it makes things simpler to record instance here.
    instance = models.ForeignKey('treemap.Instance', on_delete=models.CASCADE)

    @property
    def is_flagged(self):
        """
        Flagging is something a regular user does to suggest
        that the comment be `removed` by an adminstrator
        """
        return self.enhancedthreadedcommentflag_set.filter(
            hidden=False).exists()

    @property
    def visible_flags(self):
        return self.enhancedthreadedcommentflag_set.filter(
            hidden=False)

    @property
    def hidden_flags(self):
        return self.enhancedthreadedcommentflag_set.filter(
            hidden=True)

    def is_flagged_by_user(self, user):
        return self.enhancedthreadedcommentflag_set.filter(
            user=user, hidden=False).exists()

    def save(self, *args, **kwargs):
        if hasattr(self.content_object, 'instance'):
            self.instance = self.content_object.instance

        super(EnhancedThreadedComment, self).save(*args, **kwargs)

    class Meta:
        # Needed to break circular dependency when loading apps
        app_label = 'otm_comments'


class EnhancedThreadedCommentFlag(models.Model, Auditable):
    comment = models.ForeignKey(EnhancedThreadedComment, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    flagged_at = models.DateTimeField(auto_now_add=True)
    # whether the flag itself was hidden, NOT the related
    # comment. That is decided by `comment.is_removed`
    hidden = models.BooleanField(default=False)

    class Meta:
        # Needed to break circular dependency when loading apps
        app_label = 'otm_comments'

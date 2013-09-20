from django.contrib.gis.db import models
from treemap.models import User
from treemap.instance import Instance


class ExportJob(models.Model):
    PENDING = 0
    EMPTY_QUERYSET_ERROR = 1
    MODEL_PERMISSION_ERROR = 2
    COMPLETE = 3

    STATUS_STRINGS = {
        PENDING: 'PENDING',
        EMPTY_QUERYSET_ERROR: 'EMPTY_QUERYSET_ERROR',
        MODEL_PERMISSION_ERROR: 'MODEL_PERMISSION_ERROR',
        COMPLETE: 'COMPLETE',
    }

    STATUS_CHOICES = {
        PENDING: 'Pending',
        EMPTY_QUERYSET_ERROR: 'Query returned no results',
        MODEL_PERMISSION_ERROR: 'User has no permissions on this model',
        COMPLETE: 'Ready',
    }

    instance = models.ForeignKey(Instance)

    status = models.IntegerField(choices=STATUS_CHOICES.items(),
                                 default=PENDING)
    user = models.ForeignKey(User, null=True, blank=True)
    outfile = models.FileField(upload_to="exports/%Y/%m/%d")

    def get_url_if_ready(self):
        if self.status < self.COMPLETE:
            return None
        else:
            return self.outfile.url

# -*- coding: utf-8 -*-


import datetime

from django.contrib.gis.db import models

from treemap.models import User
from treemap.instance import Instance


class ExportJob(models.Model):
    UNCAUGHT_EXCEPTION_ERROR = -1
    PENDING = 0
    EMPTY_QUERYSET_ERROR = 1
    MODEL_PERMISSION_ERROR = 2
    COMPLETE = 3

    STATUS_STRINGS = {
        UNCAUGHT_EXCEPTION_ERROR: 'UNCAUGHT_EXCEPTION_ERROR',
        PENDING: 'PENDING',
        EMPTY_QUERYSET_ERROR: 'EMPTY_QUERYSET_ERROR',
        MODEL_PERMISSION_ERROR: 'MODEL_PERMISSION_ERROR',
        COMPLETE: 'COMPLETE',
    }

    STATUS_CHOICES = {
        UNCAUGHT_EXCEPTION_ERROR: 'Something went wrong with your export.',
        PENDING: 'Pending',
        EMPTY_QUERYSET_ERROR: 'Query returned no trees or planting sites.',
        MODEL_PERMISSION_ERROR: 'User has no permissions on this model',
        COMPLETE: 'Ready',
    }

    instance = models.ForeignKey(Instance, on_delete=models.CASCADE)

    status = models.IntegerField(choices=list(STATUS_CHOICES.items()),
                                 default=PENDING)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    outfile = models.FileField(upload_to="exports/%Y/%m/%d")
    created = models.DateTimeField(null=True, blank=True)
    modified = models.DateTimeField(null=True, blank=True)
    description = models.CharField(max_length=255)

    def save(self, *args, **kwargs):
        now = datetime.datetime.now()
        if self.pk:
            self.modified = now
        else:
            self.created = now
        super(ExportJob, self).save(*args, **kwargs)

    def get_url_if_ready(self):
        if self.status < self.COMPLETE:
            return None
        else:
            return self.outfile.url

    def complete_with(self, filename, file_obj):
        self.outfile.save(filename, file_obj)
        self.status = self.COMPLETE

    def fail(self):
        self.status = self.UNCAUGHT_EXCEPTION_ERROR

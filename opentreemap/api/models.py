# -*- coding: utf-8 -*-


import uuid
import base64
import os

from django.contrib.gis.db import models

from treemap.models import User


class APIAccessCredential(models.Model):
    access_key = models.CharField(max_length=100, null=False, blank=False)
    secret_key = models.CharField(max_length=256, null=False, blank=False)

    # If a user is specified then this credential
    # is always authorized as the given user
    #
    # If user is None this credential can access
    # any user's data if that user's username
    # and password are also provided
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)

    enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.access_key

    @classmethod
    def create(clz, user=None):
        secret_key = base64.urlsafe_b64encode(os.urandom(64)).decode()
        access_key = base64.urlsafe_b64encode(uuid.uuid4().bytes)\
                           .replace(b'=', b'').decode()

        return APIAccessCredential.objects.create(
            user=user, access_key=access_key, secret_key=secret_key)

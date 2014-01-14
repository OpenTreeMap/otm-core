# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.contrib.gis.db import models
from treemap.models import Instance, User


class OTM1UserRelic(models.Model):
    instance = models.ForeignKey(Instance)
    otm1_username = models.CharField(max_length=255)
    otm1_id = models.IntegerField()
    otm2_user = models.ForeignKey(User)
    email = models.EmailField()


class OTM1ModelRelic(models.Model):
    instance = models.ForeignKey(Instance)
    otm1_model_id = models.IntegerField()
    otm2_model_name = models.CharField(max_length=255)
    otm2_model_id = models.IntegerField()

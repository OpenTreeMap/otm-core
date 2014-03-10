# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.core.exceptions import MultipleObjectsReturned

from django.contrib.gis.db import models
from django.contrib.contenttypes.models import ContentType

from treemap.models import Instance, User


class OTM1UserRelic(models.Model):
    instance = models.ForeignKey(Instance)
    otm1_username = models.CharField(max_length=255)
    otm1_id = models.IntegerField()
    otm2_user = models.ForeignKey(User)
    email = models.EmailField()


class AbstractRelic(models.Model):
    instance = models.ForeignKey(Instance)
    otm1_model_id = models.IntegerField()
    otm2_model_id = models.IntegerField()

    def summon(self, **kwargs):
        """
        Get the OTM2 model instance that is bound to this relic
        """
        app_label = kwargs.get('app_label', 'treemap')

        try:
            model_type = ContentType.objects.get(model=self.otm2_model_name)
        except MultipleObjectsReturned:
            model_type = ContentType.objects.get(
                model=self.otm2_model_name, app_label=app_label)

        return model_type.get_object_for_this_type(pk=self.otm2_model_id)

    class Meta:
        abstract = True


class OTM1ModelRelic(AbstractRelic):
    otm2_model_name = models.CharField(max_length=255)


class OTM1CommentRelic(AbstractRelic):
    otm2_model_name = models.CharField(max_length=255,
                                       default='threadedcomment',
                                       editable=False)
    otm1_last_child_id = models.IntegerField(null=True, blank=True)

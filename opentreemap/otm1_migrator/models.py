# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.core.exceptions import MultipleObjectsReturned

from django.contrib.gis.db import models
from django.contrib.contenttypes.models import ContentType

from treemap.models import Instance, User

UNBOUND_MODEL_ID = -1




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
        unique_together = ('otm2_model_name', 'otm1_model_id', 'instance')


class OTM1ModelRelic(AbstractRelic):
    otm2_model_name = models.CharField(max_length=255)


class OTM1UserRelic(AbstractRelic):
    otm2_model_name = models.CharField(max_length=255,
                                       default='user',
                                       editable=False)
    otm1_username = models.CharField(max_length=255)
    email = models.EmailField()

    def save(self, *args, **kwargs):
        if not User.objects.filter(pk=self.otm2_model_id).exists():
            raise Exception('User not found')
        super(OTM1UserRelic, self).save(*args, **kwargs)


class OTM1CommentRelic(AbstractRelic):
    otm2_model_name = models.CharField(max_length=255,
                                       default='threadedcomment',
                                       editable=False)
    otm1_last_child_id = models.IntegerField(null=True, blank=True)

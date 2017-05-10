# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.db import models
from django.core.exceptions import ValidationError

from treemap.models import User
from treemap.instance import Instance
from treemap.json_field import JSONField


class Plan(models.Model):
    revision = models.IntegerField(default=0)
    instance = models.ForeignKey(Instance)
    owner = models.ForeignKey(User)
    name = models.TextField()
    description = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)
    creation_time = models.DateTimeField(auto_now_add=True, editable=False)
    modified_time = models.DateTimeField(auto_now=True, editable=False)
    prioritization_params = JSONField()  # Obsolete
    scenarios = JSONField(null=True, blank=True)
    zoom_lat_lng = JSONField(null=True, blank=True)

    def to_json(self):
        return {
            'id': self.id,
            'revision': self.revision,
            'owner': self.owner.username,
            'name': self.name,
            'description': self.description,
            'is_published': self.is_published,
            'scenarios': self.scenarios,
            'zoom_lat_lng': self.zoom_lat_lng,
        }

    def update(self, plan_dict):
        for key, value in plan_dict.iteritems():
            if key in ('revision', 'name', 'description', 'is_published',
                       'scenarios', 'zoom_lat_lng'):
                setattr(self, key, value)
            elif key not in ('id', 'owner'):
                raise ValidationError(
                    'Unexpected key in plan JSON: %s' % key)

    def save(self, *args, **kwargs):
        self.prioritization_params = '{"dummy": 1}'
        self.full_clean()
        super(Plan, self).save(*args, **kwargs)

    def clean(self):
        pass

    def __unicode__(self):
        return self.name

# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone

from treemap.models import MapFeature, User
from treemap.audit import Auditable
from treemap.udf import UDFModel, GeoHStoreUDFManager
from treemap.instance import Instance


class Team(models.Model):
    instance = models.ForeignKey(Instance)
    name = models.CharField(max_length=255, null=False, blank=False)


class WorkOrder(Auditable, models.Model):
    instance = models.ForeignKey(Instance)
    name = models.CharField(max_length=255, null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User)
    updated_at = models.DateTimeField(auto_now=True)

    # This value comes from `instance.work_order_sequence_number`
    reference_number = models.IntegerField()

    class Meta:
        unique_together = ('instance', 'reference_number')

    def clean(self):
        if not self.reference_number:
            raise ValidationError({
                'reference_number': [_('Reference number is required.')]})

    def save_with_user(self, user, *args, **kwargs):
        """
        Update WorkOrder fields when Task is saved.
        """
        self.full_clean()
        super(WorkOrder, self).save_with_user(user, *args, **kwargs)


class Task(UDFModel, Auditable):
    objects = GeoHStoreUDFManager()

    REQUESTED = 0
    SCHEDULED = 1
    COMPLETED = 2
    CANCELED = 3

    STATUS_CHOICES = (
        (REQUESTED, _('Requested')),
        (SCHEDULED, _('Scheduled')),
        (COMPLETED, _('Completed')),
        (CANCELED, _('Canceled')),
    )

    instance = models.ForeignKey(Instance)
    map_feature = models.ForeignKey(MapFeature)
    work_order = models.ForeignKey(WorkOrder, null=True, blank=True)
    team = models.ForeignKey(Team, null=True, blank=True)

    office_notes = models.TextField(blank=True)
    field_notes = models.TextField(blank=True)

    status = models.IntegerField(
        choices=STATUS_CHOICES,
        default=REQUESTED)

    requested_on = models.DateField()
    scheduled_on = models.DateField()
    closed_on = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User)
    updated_at = models.DateTimeField(auto_now=True)

    # This value comes from `instance.task_sequence_number`
    reference_number = models.IntegerField()

    udf_settings = {
        'Action': {
            'iscollection': False,
            'is_protected': True,
            'defaults': {
                'type': 'choice',
                'protected_choices': [
                    'Plant Tree',
                    'Remove Tree',
                ],
                'choices': [],
            }
        },
    }

    class Meta:
        unique_together = ('instance', 'reference_number')

    def clean(self):
        if not self.reference_number:
            raise ValidationError({
                'reference_number': [_('Reference number is required.')]})

    def save_with_user(self, user, *args, **kwargs):
        """
        Update WorkOrder fields when Task is saved.
        """
        self.full_clean()

        if self.work_order:
            self.work_order.updated_at = timezone.now()
            self.work_order.save_with_user(user, *args, **kwargs)

        super(Task, self).save_with_user(user, *args, **kwargs)

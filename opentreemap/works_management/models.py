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

    @property
    def model_name(self):
        return 'works_management.' + self.__class__.__name__


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
        super(WorkOrder, self).clean()
        if not self.reference_number:
            raise ValidationError({
                'reference_number': [_('Reference number is required.')]})

    def save_with_user(self, user, *args, **kwargs):
        """
        Save the WorkOrder, and
        - create audit records for its fields
        - set the reference_number to the next instance work order sequence
          (which has the side effect of updating the instance in the db)
        """
        if not self.id:
            self.reference_number = self.instance\
                .get_next_work_order_sequence()
        self.full_clean()
        super(WorkOrder, self).save_with_user(user, *args, **kwargs)

    @property
    def model_name(self):
        return 'works_management.' + self.__class__.__name__


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

    HIGH = 0
    MEDIUM = 1
    LOW = 2

    PRIORITY_CHOICES = (
        (HIGH, _('High')),
        (MEDIUM, _('Medium')),
        (LOW, _('Low')),
    )

    instance = models.ForeignKey(Instance)
    map_feature = models.ForeignKey(MapFeature)
    team = models.ForeignKey(Team, null=True, blank=True)
    work_order = models.ForeignKey(WorkOrder, default=None)

    office_notes = models.TextField(blank=True, default='')
    field_notes = models.TextField(blank=True, default='')

    status = models.IntegerField(
        choices=STATUS_CHOICES,
        default=REQUESTED)

    priority = models.IntegerField(
        choices=PRIORITY_CHOICES,
        default=MEDIUM)

    requested_on = models.DateField()
    scheduled_on = models.DateField(null=True, blank=True, default=None)
    closed_on = models.DateField(null=True, blank=True, default=None)

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

    @classmethod
    def display_name(cls, instance):
        return _('Task')

    def clean(self):
        super(Task, self).clean()
        if not self.reference_number:
            raise ValidationError({
                'reference_number': [_('Reference number is required.')]})

    def save_with_user(self, user, *args, **kwargs):
        """
        Save the WorkOrder, and
        - create audit records for its fields
        - update WorkOrder updated_at field
        - set the reference_number to the next instance work order sequence
          (which has the side effect of updating the instance in the db)
        """
        if not self.id:
            self.reference_number = self.instance.get_next_task_sequence()

        self.full_clean()

        if self.work_order:
            self.work_order.updated_at = timezone.now()
            self.work_order.save_with_user(user, *args, **kwargs)

        super(Task, self).save_with_user(user, *args, **kwargs)

    @property
    def model_name(self):
        return 'works_management.' + self.__class__.__name__

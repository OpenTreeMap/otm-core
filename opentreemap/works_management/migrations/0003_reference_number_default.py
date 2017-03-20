# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models, transaction

from treemap.models import Instance


def assign_task_reference_numbers(apps):
    """
    Populate reference_number on Tasks and update
    next sequence value on each Instance.
    """
    Task = apps.get_model('works_management', 'Task')
    tasks = Task.objects.filter(reference_number=None) \
        .values_list('id', 'instance_id')
    for task_id, instance_id in tasks:
        instance = Instance.objects.get(id=instance_id)
        reference_number = instance.get_next_task_sequence()
        # To bypass save_with_user
        Task.objects.filter(id=task_id) \
            .update(reference_number=reference_number)


def assign_work_order_reference_numbers(apps):
    """
    Populate reference_number on WorkOrders and update
    next sequence value on each Instance.
    """
    WorkOrder = apps.get_model('works_management', 'WorkOrder')
    work_orders = WorkOrder.objects.filter(reference_number=None) \
        .values_list('id', 'instance_id')
    for work_order_id, instance_id in work_orders:
        instance = Instance.objects.get(id=instance_id)
        reference_number = instance.get_next_work_order_sequence()
        # To bypass save_with_user
        WorkOrder.objects.filter(id=work_order_id) \
            .update(reference_number=reference_number)


def forward(apps, schema_editor):
    """
    Populate nullable reference_number fields on WM models.
    """
    assign_task_reference_numbers(apps)
    assign_work_order_reference_numbers(apps)


def backward(apps, schema_editor):
    # Nothing to do.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('works_management', '0002_reference_number_field'),
    ]

    operations = [
        migrations.RunPython(forward, backward)
    ]

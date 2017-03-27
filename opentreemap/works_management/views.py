# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import ugettext as _

from opentreemap.util import dotted_split

# from treemap.lib.object_caches import udf_defs
from treemap.audit import bulk_create_with_user
from treemap.models import Plot
from treemap.search import Filter
from treemap.udf import UserDefinedFieldDefinition
from treemap.util import package_field_errors

from works_management.forms import TaskForm
from works_management.models import WorkOrder, Task


def work_orders(request, instance):
    return {}


WMM_MODEL_NAME = 'task'


def _udf_defs_from_db(instance, model_name):
    defs = UserDefinedFieldDefinition.objects.filter(instance=instance)
    if model_name:
        defs = defs.filter(model_type=model_name)
    return list(defs)


@transaction.atomic
def create_tasks(request, instance):
    '''
    Bulk create Task objects corresponding to Plot objects found in
    a search using the POST data search query, with field values
    obtained from the POST data inline-edit form items.

    May raise ValidationError.

    On success, returns an empty dict.
    '''
    request_dict = json.loads(request.body)
    filter_str = request_dict.get('q', '')
    if not filter_str:
        raise ValidationError(_('A search is required'))
    form_fields = request_dict.get('form_fields', '')
    if not form_fields:
        raise ValidationError(_('The task form is required'))

    SPLIT_TEMPLATE = 'Malformed request - invalid field %s'

    work_order = None
    create_kwargs = {
        'instance': instance.pk,
        'requested_on': timezone.now(),
        'created_by': request.user.pk,
        'status': Task.REQUESTED,
        'priority': Task.MEDIUM
    }

    udf_kwargs = {}

    validation_errors = {}

    if 'task.work_order_id' in form_fields and \
            form_fields['task.work_order_id'] is not None and \
            0 < len(form_fields['task.work_order_id']):
        work_order = WorkOrder.objects.get(form_fields['task.work_order_id'])
        del form_fields['task.work_order_id']
        if 'workorder.name' in form_fields:
            del form_fields['workorder.name']
    elif 'workorder.name' in form_fields and \
            form_fields['workorder.name'] is not None and \
            0 < len(form_fields['workorder.name']):
        work_order = WorkOrder(instance=instance,
                               name=form_fields['workorder.name'],
                               created_by=request.user,
                               created_at=timezone.now())
        work_order.save_with_user(request.user)
        del form_fields['workorder.name']
        if 'task.work_order_id' in form_fields:
            del form_fields['task.work_order_id']
    else:
        raise ValidationError(_('A work order must be specified'))

    def validate_field_name(identifier):
        MODEL_NAME = 'works_management.Task'
        MESSAGE_FIELD = SPLIT_TEMPLATE % identifier
        is_udf = False
        object_name, field = dotted_split(identifier, 2,
                                          failure_format_string=SPLIT_TEMPLATE)
        if object_name != WMM_MODEL_NAME:
            raise TypeError(_('Invalid field %s') % MESSAGE_FIELD)
        if field.startswith('udf:'):
            field = field[4:]

            if field not in [udfd.name for udfd
                             in _udf_defs_from_db(instance, MODEL_NAME)]:
                raise AttributeError(
                    _('No custom field with name %s') % MESSAGE_FIELD)
            is_udf = True

        elif field not in TaskForm._meta.fields:
            raise AttributeError(_('Invalid field %s') % MESSAGE_FIELD)
        return field, is_udf

    for (identifier, value) in form_fields.iteritems():
        field, is_udf = validate_field_name(identifier)
        if is_udf:
            udf_kwargs[field] = value
        else:
            create_kwargs[field] = value
    create_kwargs['udfs'] = udf_kwargs

    try:
        plot_qs = Filter(filter_str, json.dumps(['Plot']), instance)\
            .get_objects(Plot)
        plot_count = plot_qs.count()
    except:
        plot_count = 0

    if 0 == plot_count:
        validation_errors['globalErrors'] = [_('No planting sites were found')]
        create_kwargs['reference_number'] = instance.task_sequence_number
    else:
        create_kwargs['reference_number'] = \
            instance.get_next_task_sequence(plot_count)
    create_kwargs['work_order'] = work_order.pk

    task_form = TaskForm(create_kwargs)
    if not task_form.is_valid():
        form_errors = task_form.errors.copy()
        if 'udfs' in form_errors:
            udf_errors = form_errors['udfs']
            del form_errors['udfs']
            for message in udf_errors:
                form_errors.update(json.loads(message))
        validation_errors.update(package_field_errors(
            WMM_MODEL_NAME,
            ValidationError(form_errors)))

    if validation_errors:
        raise ValidationError(validation_errors)

    cleaned_data = task_form.cleaned_data.copy()

    def task_with_plot(plot):
        task_args = {'map_feature': plot}
        task_args.update(cleaned_data)
        t = Task(**task_args)
        cleaned_data['reference_number'] += 1
        return t

    tasks = [task_with_plot(plot) for plot in plot_qs]
    bulk_create_with_user(tasks, request.user)

    return {}

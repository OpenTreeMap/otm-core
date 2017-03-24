# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json

from django.forms import ModelForm
from django.core.exceptions import ValidationError

from works_management.models import Task


class TaskFormException(Exception):
    pass


# Use a ModelForm strictly for validation,
# in order to validate the input without having to create all the tasks
# for bulk creation, and also do the bulk_create.
class TaskForm(ModelForm):
    class Meta:
        model = Task
        fields = ['instance', 'work_order', 'team', 'office_notes',
                  'field_notes', 'status', 'requested_on', 'created_by',
                  'reference_number', 'priority', 'udfs']

    def add_error(self, field, error):
        if hasattr(error, 'message_dict'):
            # udf messages in the error.message_dict need to be added
            # with the key 'udfs' in order for ModelForm to
            # associate them with the 'udfs' field.
            new_message_dict = {'udfs': []}
            for key, message in error.message_dict.items():
                if key.startswith('udf:'):
                    # ValidationError compresses its messages
                    # so that only strings remain for each message_dict key.
                    # That would lose the original key, so preserve it
                    # in a json.dumps().
                    new_message_dict['udfs'].append(json.dumps({
                        key: message}))
                else:
                    new_message_dict[key] = message
            if new_message_dict['udfs']:
                error = ValidationError(new_message_dict)
        super(TaskForm, self).add_error(field, error)

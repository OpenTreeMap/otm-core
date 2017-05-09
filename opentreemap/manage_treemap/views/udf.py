# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

import json

from django.db import transaction
from django.http import (HttpResponse, HttpResponseBadRequest,
                         HttpResponseNotFound)
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _

from opentreemap.util import json_from_request

from treemap.udf import (UserDefinedFieldDefinition, safe_get_udf_model_class,
                         UserDefinedCollectionValue)
from treemap.util import to_model_name
from treemap.exceptions import JSONResponseForbidden
from treemap.lib.object_caches import udf_defs
import treemap.lib.udf as lib

from manage_treemap.views import add_udf_notification, remove_udf_notification


def udf_update_choice(request, instance, udf_id):
    params = json_from_request(request)

    udf = get_object_or_404(UserDefinedFieldDefinition, pk=udf_id)

    _udf_update_choice(udf, instance, params)

    return HttpResponse(_('Updated Custom Field'))


@transaction.atomic
def udf_bulk_update(request, instance):
    '''
    udf_bulk_update(request, instance)

    'instance': a treemap instance
    'request': an HTTP request object whose body is a JSON representation
               of a dict containing the key 'choice_changes'.

    choice_changes is a list of directives per choice-type
    UserDefinedFieldDefinition.  Each directive is a dict, defined as follows:
    {
        'id': id of a UserDefinedFieldDefinition,
        'changes': a list of changes to make to the UserDefinedFieldDefinition
                   with that id.
    }

    Each change is either a delete, rename, or add request pertaining to
    one choice of the UserDefinedFieldDefinition.

    There should be no more than one change per choice,
    and the list should be ordered as deletes, then renames, then adds.
    See the docstring for `_udf_update_choice` for the structure of each
    choice change parameter.
    '''
    params = json.loads(request.body)
    choice_changes = params.get('choice_changes', None)

    if choice_changes:
        choice_map = {int(param['id']): param['changes']
                      for param in choice_changes}
        udfds = [udf for udf in udf_defs(instance)
                 if udf.pk in choice_map.keys()]

        # Update one at a time rather than doing bulk_update.
        # There won't be that many of them, and we need to go through
        # all the UDF machinery to update models and audit records.

        # Also, assume that the frontend will not send more than one change
        # (rename or delete) for the same choice,
        # or changes (rename or delete) for any new choices.
        for udf in udfds:
            for params in choice_map[udf.pk]:
                _udf_update_choice(udf, instance, params)

    return HttpResponse(_('Updated Custom Fields'))


def _udf_update_choice(udf, instance, params):
    '''
    _udf_update_choice(udf, instance, params)

    `udf`: a choice-type UserDefinedFieldDefinition
    `instance`: a treemap Instance
    `params`: a dict representing changes to make to the udf, as follows.
    {
        'action':         ('delete'|'rename'|'add')
        'subfield':       empty string for a scalar udf, or
                          the key of interest in a collection udf.
        'original_value': the name of the choice on entry to this function,
                          empty string if 'action' is 'add'.
        'new_value':      the name of the choice on exit from this function,
                          empty string if 'action is 'delete'.
    }
    '''
    editable_udf_model_names = {clz.__name__ for clz in
                                instance.editable_udf_models()['all']}

    if udf.model_type not in editable_udf_model_names:
        return JSONResponseForbidden()

    action = params['action']

    subfield = params.get('subfield', None) or None

    if action == 'delete':
        udf.delete_choice(
            params['original_value'], name=subfield)
    elif action == 'rename':
        udf.update_choice(
            params['original_value'],
            params['new_value'],
            name=subfield)
    elif action == 'add':
        udf.add_choice(
            params['new_value'],
            name=subfield)
    else:
        raise ValidationError(
            {'action': ['Invalid action']})


def udf_list(request, instance):
    editable_udf_models = instance.editable_udf_models()
    udf_models = \
        sorted([{'name': clz.__name__,
                 'display_name': clz.display_name(instance)}
                for clz in editable_udf_models['core']],
               key=lambda model: model['name'],
               reverse=True) + \
        sorted([{'name': clz.__name__,
                 'display_name': clz.display_name(instance)}
                for clz in editable_udf_models['gsi']],
               key=lambda model: model['name'])

    editable_gsi_models = [clz.__name__ for clz in editable_udf_models['gsi']]

    udf_model_names = sorted([model['name'] for model in udf_models])

    udfs = sorted([udf for udf in udf_defs(instance)
                   if udf.model_type in udf_model_names],
                  key=lambda udf: (udf.model_type, udf.iscollection,
                                   udf.name))

    def dict_update(d1, d2):
        d1.update(d2)
        return d1

    udf_models = [dict_update(model, {
        'specs': [{'udf': udf, 'datatype': _get_type_display(udf)}
                  for udf in udfs if udf.model_type == model['name']]
        }) for model in udf_models]

    return {
        "udf_models": udf_models,
        "editable_gsi_models": editable_gsi_models
    }


@transaction.atomic
def udf_create(request, instance):
    params = json_from_request(request)
    udf = lib.udf_create(params, instance)
    add_udf_notification(instance, to_model_name(udf.full_name))
    return udf_context(instance, udf)


def udf_delete_popup(request, instance, udf_id):
    udf_def = get_object_or_404(UserDefinedFieldDefinition, pk=udf_id,
                                instance=instance)
    return udf_context(instance, udf_def)


def udf_context(instance, udf_def):
    if udf_def.iscollection:
        udf_uses = UserDefinedCollectionValue.objects\
            .filter(field_definition=udf_def)\
            .count()
    else:
        Model = safe_get_udf_model_class(udf_def.model_type)
        udf_uses = Model.objects.filter(instance=instance)\
                                .filter(udfs__has_key=udf_def.name)\
                                .count()

    return {
        'udf': udf_def,
        'udf_uses': udf_uses,
        'datatype': _get_type_display(udf_def),
    }


@transaction.atomic
def udf_delete(request, instance, udf_id):
    try:
        udf_def = UserDefinedFieldDefinition.objects.get(pk=udf_id,
                                                         instance=instance)
    except UserDefinedFieldDefinition.DoesNotExist:
        return HttpResponseNotFound(_("Field does not exist"))

    if udf_def.iscollection:
        return HttpResponseBadRequest(_("Cannot delete default fields"))

    remove_udf_notification(instance, to_model_name(udf_def.full_name))

    udf_def.delete()

    return HttpResponse(_("Deleted custom field"))


def remove_udf_notifications(request, instance):
    instance.config['udf_notifications'] = []
    instance.save()

    return {'success': True}

TYPE_MAP = {
    "float": _("Decimal Number"),
    "int": _("Integer Number"),
    "string": _("Text"),
    "choice": _("List of Choices"),
    "multichoice": _("List of Choices (Select Multiple)"),
    "date": _("Date"),
    "Action": _("Action"),
}


def _get_type_display(udf):
    datatype_dict = udf.datatype_dict
    if udf.iscollection:
        # In theory there could be more datatype dicts
        # but in practice, there is only ever one,
        # and it represents a Stewardship Action.
        return TYPE_MAP['Action']
    data_type = datatype_dict.get('type', 'Action')
    return TYPE_MAP[data_type]
